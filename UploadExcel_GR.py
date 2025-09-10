# Alias del archivo original conservando la lógica.
"""Archivo principal de la aplicación (antes UploadExcel_Monse3GR.py).

Se consolidó toda la lógica aquí para evitar el uso de un alias.
Las credenciales y claves deben venir de variables de entorno (.env).
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, session, flash
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
from functools import wraps
from sqlalchemy import text
import subprocess
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import hashlib
import re
import csv
import secrets
import string

REQUIRED_ENV_VARS = ['DB_SERVER', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'APP_SECRET_KEY']
missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
if missing:
        raise RuntimeError(f"Faltan variables de entorno obligatorias: {', '.join(missing)}")

app = Flask(__name__)
app.secret_key = os.getenv('APP_SECRET_KEY')  # Necesaria para las sesiones

# Configuración de la base de datos vía variables de entorno
DB_SERVER = os.getenv('DB_SERVER')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Token opcional para habilitar la página de migración vía URL (?token=...)
MIGRATION_TOKEN = os.getenv('MIGRATION_TOKEN', '')
ADMIN_BOOTSTRAP_TOKEN = os.getenv('ADMIN_BOOTSTRAP_TOKEN', '')
REGISTRATION_TOKEN = os.getenv('REGISTRATION_TOKEN', '')

# Utilidades de passwords
def is_werkzeug_hash(pw: str) -> bool:
	return bool(pw) and (pw.startswith('pbkdf2:') or pw.startswith('scrypt:'))

def is_sha256_hex(pw: str) -> bool:
	if not pw:
		return False
	cand = pw[2:] if pw.lower().startswith('0x') else pw
	return re.fullmatch(r'[A-Fa-f0-9]{64}', cand or '') is not None

def gen_temp_password(length: int = 12) -> str:
	alphabet = string.ascii_letters + string.digits + "!@#$%*?"
	return ''.join(secrets.choice(alphabet) for _ in range(length))

def has_migration_access(req) -> bool:
	# Permitir si está logueado con nivel 2 o si proporciona el token correcto
	if 'user_id' in session and session.get('nivel_acceso') == 2:
		return True
	token = (req.args.get('token') or req.form.get('token') or '').strip()
	return bool(MIGRATION_TOKEN and token and token == MIGRATION_TOKEN)

# Normaliza cualquier representación de password desde la BD a str
def normalize_pw(pw) -> str:
	if pw is None:
		return ''
	if isinstance(pw, bytes):
		# intentar decodificar como texto (utf-16le primero por SQL Server NVARCHAR -> VARBINARY)
		for enc in ('utf-16le','utf-8','latin-1'):
			try:
				s = pw.decode(enc, errors='ignore').strip()
				if s:
					return s
			except Exception:
				continue
		return pw.hex()
	return str(pw).strip()

# Permitir registro si: no hay usuarios en la tabla, o si hay token de registro válido
def can_register(req) -> tuple[bool, str]:
	try:
		with db.engine.connect() as conn:
			res = conn.execute(text("SELECT COUNT(*) FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]"))
			total = int(res.scalar() or 0)
		if total == 0:
			return True, 'empty'
		# si hay token configurado, validar
		if REGISTRATION_TOKEN:
			tok = (req.args.get('token') or req.form.get('token') or '').strip()
			if tok == REGISTRATION_TOKEN:
				return True, 'token'
		return False, 'disabled'
	except Exception as e:
		return False, f'error: {e}'

# Detecta si la columna Password es VARBINARY para decidir cómo almacenar el hash
_PASS_IS_BINARY = None
def password_is_binary() -> bool:
	global _PASS_IS_BINARY
	if _PASS_IS_BINARY is not None:
		return _PASS_IS_BINARY
	try:
		with db.engine.connect() as conn:
			row = conn.execute(text("""
				SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='CierreSucursales_Control_Accesos_Web' AND COLUMN_NAME='Password'
			"""))
			dtype = (row.scalar() or '').lower()
			_PASS_IS_BINARY = dtype == 'varbinary'
	except Exception:
		_PASS_IS_BINARY = False
	return _PASS_IS_BINARY

def prepare_pw_value(pwhash: str):
	# Permite pasar bytes directo
	if isinstance(pwhash, (bytes, bytearray, memoryview)):
		return bytes(pwhash)
	# Si la columna es binaria y tenemos un string (por compatibilidad), codificar en UTF-16LE
	if password_is_binary():
		return str(pwhash).encode('utf-16le')
	return pwhash

# Cache columnas de la tabla
_COLS_CACHE = None
def get_table_columns() -> set:
	global _COLS_CACHE
	if _COLS_CACHE is not None:
		return _COLS_CACHE
	try:
		with db.engine.connect() as conn:
			rows = conn.execute(text("""
				SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='CierreSucursales_Control_Accesos_Web'
			"""))
			_COLS_CACHE = {r[0] for r in rows}
	except Exception:
		_COLS_CACHE = set()
	return _COLS_CACHE

def make_db_digest(password: str, use_salt: bool = True) -> tuple[bytes, bytes]:
	if use_salt:
		salt = os.urandom(16)
		digest = hashlib.sha256(salt + password.encode('utf-8')).digest()
		return digest, salt
	else:
		# Unsalted digest (only if schema has no PasswordSalt column)
		salt = b''
		digest = hashlib.sha256(password.encode('utf-8')).digest()
		return digest, salt

def verify_db_digest(password: str, digest: bytes, salt: bytes | None) -> bool:
	try:
		salt_bytes = bytes(salt) if (salt is not None and len(salt) > 0) else b''
		if salt_bytes:
			calc = hashlib.sha256(salt_bytes + password.encode('utf-8')).digest()
		else:
			calc = hashlib.sha256(password.encode('utf-8')).digest()
		return calc == bytes(digest)
	except Exception:
		return False

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Logging rotativo
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, 'app.log')
if not app.logger.handlers:
	handler = RotatingFileHandler(log_path, maxBytes=2*1024*1024, backupCount=5, encoding='utf-8')
	formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s')
	handler.setFormatter(formatter)
	handler.setLevel(logging.INFO)
	app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Logger inicializado')

# Context processor: provide current_year for templates
@app.context_processor
def inject_now():
	try:
		return { 'current_year': datetime.now().year }
	except Exception:
		return { 'current_year': '' }

# Función para verificar si un usuario está logueado
def login_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if 'user_id' not in session:
			flash('Por favor inicie sesión para acceder a esta página', 'danger')
			return redirect(url_for('login'))
		return f(*args, **kwargs)
	return decorated_function

# Función para verificar si un usuario tiene nivel de acceso 2
def nivel_acceso_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if session.get('nivel_acceso') != 2:
			flash('No tiene permisos para acceder a esta página', 'danger')
			return redirect(url_for('login'))
		return f(*args, **kwargs)
	return decorated_function

# Columnas esperadas del Excel
EXPECTED_COLUMNS = [
	'Departamento', 'Soc.', 'Act. Fijo', 'Clase', 'Fe. Capit.',
	'Denominacion del activo fijo', 'Val. Cont.', 'Mon.', 'Orden',
	'Ceco', 'Ceco Destino', 'Tipo de Activo', 'Correo 1',
	'Nivel Correo 1', 'Correo 2', 'Nivel Correo 2', 'Correo 3',
	'Nivel Correo 3', 'Correo 4', 'Nivel Correo 4', 'Correo 5',
	'Nivel Correo 5', 'Farmacia', 'Domicilio', 'Ciudad', 'Estado',
	'GerenteOP', 'Director'
]

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		username = request.form.get('username')
		password = request.form.get('password')
		# Recuperar password y validar contra múltiples formatos admitidos
		# - Hash de Werkzeug (scrypt/pbkdf2) -> check_password_hash
		# - SHA2_256 en HEX (por inserciones via SQL) -> hashlib.sha256(...).hexdigest()
		# - Texto plano legacy -> comparación directa
		# Si la columna Password es VARBINARY, traer también PasswordSalt (si existe)
		binary_pw = password_is_binary()
		cols = get_table_columns()
		if binary_pw:
			extra_salt = ", [PasswordSalt]" if 'PasswordSalt' in cols else ", CAST(NULL AS VARBINARY(16)) AS PasswordSalt"
		else:
			extra_salt = ""
		query = text(f"""
		SELECT [Usuario], [Password], [Nivel Acceso], [Nombre], [Apellido Paterno],[Correo]{extra_salt}
		FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
		WHERE [Usuario] = :username
		""")
		try:
			with db.engine.connect() as conn:
				row = conn.execute(query, {'username': username}).fetchone()
			if row:
				valid = False
				if binary_pw:
					# row indices: 0 Usuario, 1 Password (bytes), 2 Nivel, 3 Nombre, 4 ApPaterno, 5 Correo, 6 PasswordSalt (bytes or None)
					digest = row[1]
					salt = row[6] if len(row) >= 7 else None
					# Caso 1: Password ya es digest (32 bytes)
					if isinstance(digest, (bytes, bytearray)) and len(digest) == 32:
						valid = verify_db_digest(password, bytes(digest), salt)
					# Caso 2: Password contiene datos de texto codificados en VARBINARY (utf-16le). Intentar migrar.
					if not valid and isinstance(digest, (bytes, bytearray)) and len(digest) != 32:
						stored_pw_str = normalize_pw(bytes(digest))
						# Intentar como werkzeug
						try:
							if stored_pw_str and check_password_hash(stored_pw_str, password):
								valid = True
								# Migrar a digest+salt binario
								use_salt = 'PasswordSalt' in cols
								nd, ns = make_db_digest(password, use_salt=use_salt)
								with db.engine.begin() as c2:
									upd = "UPDATE CierreSucursales_Control_Accesos_Web SET [Password]=:pw"
									params = {'pw': nd, 'u': username}
									if 'PasswordSalt' in cols:
										upd += ", [PasswordSalt]=:salt"; params['salt'] = ns
									if 'PasswordLastChanged' in cols:
										upd += ", [PasswordLastChanged]=GETDATE()"
									if 'IsLegacyPassword' in cols:
										upd += ", [IsLegacyPassword]=0"
									upd += " WHERE [Usuario]=:u"
									c2.execute(text(upd), params)
								app.logger.info(f"Password migrado de werkzeug string a digest+salt binario para {username}")
						except Exception:
							pass
						# Intentar como SHA256 hex
						if not valid and stored_pw_str:
							cand = stored_pw_str[2:] if stored_pw_str.lower().startswith('0x') else stored_pw_str
							if re.fullmatch(r'[A-Fa-f0-9]{64}', cand or ''):
								sha_hex = hashlib.sha256(password.encode('utf-8')).hexdigest()
								if sha_hex.lower() == cand.lower():
									valid = True
									try:
										use_salt = 'PasswordSalt' in cols
										nd, ns = make_db_digest(password, use_salt=use_salt)
										with db.engine.begin() as c3:
											upd = "UPDATE CierreSucursales_Control_Accesos_Web SET [Password]=:pw"
											params = {'pw': nd, 'u': username}
											if 'PasswordSalt' in cols:
												upd += ", [PasswordSalt]=:salt"; params['salt'] = ns
											if 'PasswordLastChanged' in cols:
												upd += ", [PasswordLastChanged]=GETDATE()"
											if 'IsLegacyPassword' in cols:
												upd += ", [IsLegacyPassword]=0"
											upd += " WHERE [Usuario]=:u"
											c3.execute(text(upd), params)
										app.logger.info(f"Password (SHA256 HEX) migrado a digest+salt para {username}")
									except Exception as me:
										app.logger.warning(f"No se pudo migrar SHA256->digest para {username}: {me}")
						# Intentar como texto plano legacy
						if not valid and stored_pw_str and stored_pw_str == password:
							valid = True
							try:
								use_salt = 'PasswordSalt' in cols
								nd, ns = make_db_digest(password, use_salt=use_salt)
								with db.engine.begin() as c4:
									upd = "UPDATE CierreSucursales_Control_Accesos_Web SET [Password]=:pw"
									params = {'pw': nd, 'u': username}
									if 'PasswordSalt' in cols:
										upd += ", [PasswordSalt]=:salt"; params['salt'] = ns
									if 'PasswordLastChanged' in cols:
										upd += ", [PasswordLastChanged]=GETDATE()"
									if 'IsLegacyPassword' in cols:
										upd += ", [IsLegacyPassword]=0"
									upd += " WHERE [Usuario]=:u"
									c4.execute(text(upd), params)
								app.logger.info(f"Password legacy migrado a digest+salt para {username}")
							except Exception as me:
								app.logger.warning(f"No se pudo migrar legacy->digest para {username}: {me}")
				else:
					stored_pw = normalize_pw(row[1])
					# 1) Intentar validar como hash de Werkzeug (scrypt/pbkdf2)
					try:
						if stored_pw:
							valid = check_password_hash(stored_pw, password)
					except Exception:
						valid = False
					# 2) SHA256 HEX
					if not valid and stored_pw:
						cand = stored_pw[2:] if stored_pw.lower().startswith('0x') else stored_pw
						if re.fullmatch(r'[A-Fa-f0-9]{64}', cand or ''):
							sha_hex = hashlib.sha256(password.encode('utf-8')).hexdigest()
							if sha_hex.lower() == cand.lower():
								valid = True
								try:
									new_hash = generate_password_hash(password)
									with db.engine.begin() as c2:
										c2.execute(text("UPDATE CierreSucursales_Control_Accesos_Web SET [Password]=:pw WHERE [Usuario]=:u"),
												   {'pw': prepare_pw_value(new_hash), 'u': username})
									app.logger.info(f"Password (SHA256 HEX) migrado a hash Werkzeug para usuario {username}")
								except Exception as me:
									app.logger.warning(f"No se pudo migrar password SHA256->Werkzeug para {username}: {me}")
					# 3) Texto plano legacy
					if not valid and stored_pw:
						if stored_pw == password:
							valid = True
							try:
								new_hash = generate_password_hash(password)
								with db.engine.begin() as c3:
									c3.execute(text("UPDATE CierreSucursales_Control_Accesos_Web SET [Password]=:pw WHERE [Usuario]=:u"),
											   {'pw': prepare_pw_value(new_hash), 'u': username})
								app.logger.info(f"Password legacy migrado a hash para usuario {username}")
							except Exception as me:
								app.logger.warning(f"No se pudo migrar password legacy->hash para {username}: {me}")
				if valid:
					nivel_acceso = int(row[2])
					if nivel_acceso == 2:
						session['user_id'] = row[0]
						session['nombre_completo'] = f"{row[3]} {row[4]}"
						session['nivel_acceso'] = nivel_acceso
						session['email'] = row[5]
						return redirect(url_for('dashboard'))
					else:
						flash('No tiene permisos para acceder al sistema', 'danger')
				else:
					flash('Usuario o contraseña incorrectos', 'danger')
		except Exception as e:
			flash(f'Error: {str(e)}', 'danger')
	return render_template('login.html')

@app.route('/logout')
def logout():
	session.clear()
	return redirect(url_for('login'))

@app.route('/')
def index():
	return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
	if 'user_id' in session and session.get('nivel_acceso') == 2:
		return render_template('dashboard2.html')
	flash('Acceso no autorizado', 'danger')
	return redirect(url_for('login'))

# --- Registro público (controlado) para crear usuario ---
@app.route('/signup', methods=['GET'])
def signup_view():
	allowed, reason = can_register(request)
	if not allowed:
		flash('Registro deshabilitado', 'warning')
		return redirect(url_for('login'))
	return render_template('signup.html', reason=reason)

@app.route('/signup', methods=['POST'])
def signup_post():
	allowed, _ = can_register(request)
	if not allowed:
		flash('Registro deshabilitado', 'warning')
		return redirect(url_for('login'))
	usuario = (request.form.get('usuario') or '').strip()
	correo = (request.form.get('correo') or '').strip()
	nombre = (request.form.get('nombre') or '').strip()
	ap_pat = (request.form.get('apellido_paterno') or '').strip()
	ap_mat = (request.form.get('apellido_materno') or '').strip()
	password = (request.form.get('password') or '').strip()
	token = (request.form.get('token') or '').strip()
	if REGISTRATION_TOKEN and token and token != REGISTRATION_TOKEN:
		flash('Token inválido', 'danger')
		return redirect(url_for('signup_view'))
	if not all([usuario, correo, nombre, ap_pat, password]):
		flash('Completa los campos obligatorios', 'danger')
		return redirect(url_for('signup_view'))
	if len(password) < 6:
		flash('La contraseña debe tener al menos 6 caracteres', 'danger')
		return redirect(url_for('signup_view'))
	try:
		with db.engine.begin() as conn:
			# Evitar duplicados por usuario/correo
			exists = conn.execute(text("""
				SELECT 1 FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
				WHERE [Usuario]=:u OR [Correo]=:c
			"""), {'u': usuario, 'c': correo}).fetchone()
			if exists:
				flash('Usuario o correo ya existen', 'danger')
				return redirect(url_for('signup_view'))
			cols = get_table_columns()
			if password_is_binary():
				use_salt = 'PasswordSalt' in cols
				digest, salt = make_db_digest(password, use_salt=use_salt)
				base_cols = ["Nombre","Apellido Paterno","Apellido Materno","Usuario","Password","Departamento","Nivel Acceso","Correo"]
				base_vals = [":n",":ap",":am",":u",":p","'SISTEMAS'","2",":c"]
				params = {'n': nombre, 'ap': ap_pat, 'am': ap_mat, 'u': usuario, 'p': digest, 'c': correo}
				if 'PasswordSalt' in cols:
					base_cols.append('PasswordSalt'); base_vals.append(':s'); params['s'] = salt
				if 'PasswordLastChanged' in cols:
					base_cols.append('PasswordLastChanged'); base_vals.append('GETDATE()')
				if 'IsLegacyPassword' in cols:
					base_cols.append('IsLegacyPassword'); base_vals.append('0')
				cols_sql = ",".join(f"[{c}]" for c in base_cols)
				vals_sql = ",".join(base_vals)
				conn.execute(text(f"INSERT INTO [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] ({cols_sql}) VALUES ({vals_sql})"), params)
			else:
				hash_pw = generate_password_hash(password)
				pw_val = prepare_pw_value(hash_pw)
				conn.execute(text("""
					INSERT INTO [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
					([Nombre],[Apellido Paterno],[Apellido Materno],[Usuario],[Password],[Departamento],[Nivel Acceso],[Correo])
					VALUES (:n,:ap,:am,:u,:p,'SISTEMAS',2,:c)
				"""), {'n': nombre, 'ap': ap_pat, 'am': ap_mat, 'u': usuario, 'p': pw_val, 'c': correo})
		flash('Usuario creado, inicia sesión', 'success')
		return redirect(url_for('login'))
	except Exception as e:
		flash(f'Error al registrar: {e}', 'danger')
		return redirect(url_for('signup_view'))

# --- Bootstrap de administrador si la tabla está vacía ---
@app.route('/bootstrap_admin', methods=['GET','POST'])
def bootstrap_admin():
	# Permitir sólo si la tabla está vacía y se provee token correcto
	with db.engine.connect() as conn:
		res = conn.execute(text("SELECT COUNT(*) AS c FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]"))
		try:
			total = int(res.scalar() or 0)
		except Exception:
			row = res.fetchone()
			total = int(row[0]) if row else 0
	if total > 0:
		flash('Ya existen usuarios; bootstrap deshabilitado.', 'warning')
		return redirect(url_for('login'))
	if request.method == 'GET':
		# Si no hay token configurado en el entorno, se permite continuar (escenario de arranque)
		return render_template('bootstrap_admin.html')
	# POST
	token = (request.form.get('token') or '').strip()
	# Si hay token configurado, debe coincidir; si no hay token configurado, permitir
	if ADMIN_BOOTSTRAP_TOKEN:
		if token != ADMIN_BOOTSTRAP_TOKEN:
			flash('Token inválido', 'danger')
			return redirect(url_for('bootstrap_admin'))
	usuario = (request.form.get('usuario') or 'admin').strip()
	password = (request.form.get('password') or '').strip()
	correo = (request.form.get('correo') or 'admin@example.com').strip()
	nombre = (request.form.get('nombre') or 'Admin').strip()
	ap_pat = (request.form.get('apellido_paterno') or 'Sistema').strip()
	ap_mat = (request.form.get('apellido_materno') or '').strip()
	if len(password) < 6:
		flash('La contraseña debe tener al menos 6 caracteres', 'danger')
		return redirect(url_for('bootstrap_admin'))
	try:
		with db.engine.begin() as conn:
			# Evita esperas prolongadas por bloqueos
			conn.execute(text("SET LOCK_TIMEOUT 5000;"))
			# Detectar columnas opcionales
			cols_rows = conn.execute(text("""
				SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='CierreSucursales_Control_Accesos_Web'
			""")).fetchall()
			colset = {c[0] for c in cols_rows}
			base_cols = ["Nombre","Apellido Paterno","Apellido Materno","Usuario","Password","Departamento","Nivel Acceso","Correo"]
			base_vals = [":n",":ap",":am",":u",":p","'SISTEMAS'","2",":c"]
			params = { 'n':nombre,'ap':ap_pat,'am':ap_mat,'u':usuario,'c':correo }
			if password_is_binary():
				use_salt = 'PasswordSalt' in colset
				digest, salt = make_db_digest(password, use_salt=use_salt)
				params['p'] = digest
				if 'PasswordSalt' in colset:
					base_cols.append('PasswordSalt'); base_vals.append(':s'); params['s'] = salt
				if 'PasswordLastChanged' in colset:
					base_cols.append('PasswordLastChanged'); base_vals.append('GETDATE()')
				if 'IsLegacyPassword' in colset:
					base_cols.append('IsLegacyPassword'); base_vals.append('0')
			else:
				hash_pw = generate_password_hash(password)
				params['p'] = prepare_pw_value(hash_pw)
				if 'PasswordSalt' in colset:
					base_cols.append('PasswordSalt'); base_vals.append('NULL')
				if 'PasswordLastChanged' in colset:
					base_cols.append('PasswordLastChanged'); base_vals.append('GETDATE()')
				if 'IsLegacyPassword' in colset:
					base_cols.append('IsLegacyPassword'); base_vals.append('0')
			cols_sql = ",".join(f"[{c}]" for c in base_cols)
			vals_sql = ",".join(base_vals)
			conn.execute(text(f"INSERT INTO [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] ({cols_sql}) VALUES ({vals_sql})"), params)
		flash('Usuario administrador creado. Ya puedes iniciar sesión.', 'success')
	except Exception as e:
		flash(f'Error al crear admin: {e}', 'danger')
	return redirect(url_for('login'))

# Variante JSON para diagnóstico/automatización
@app.route('/bootstrap_admin_api', methods=['POST'])
def bootstrap_admin_api():
	try:
		with db.engine.connect() as conn:
			res = conn.execute(text("SELECT COUNT(*) FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]"))
			total = int(res.scalar() or 0)
		if total > 0:
			return jsonify({'ok': False, 'message': 'Ya existen usuarios'}), 400
		if ADMIN_BOOTSTRAP_TOKEN:
			token = (request.form.get('token') or '').strip()
			if token != ADMIN_BOOTSTRAP_TOKEN:
				return jsonify({'ok': False, 'message': 'Token inválido'}), 403
		usuario = (request.form.get('usuario') or 'admin').strip()
		password = (request.form.get('password') or '').strip()
		correo = (request.form.get('correo') or 'admin@example.com').strip()
		nombre = (request.form.get('nombre') or 'Admin').strip()
		ap_pat = (request.form.get('apellido_paterno') or 'Sistema').strip()
		ap_mat = (request.form.get('apellido_materno') or '').strip()
		if len(password) < 6:
			return jsonify({'ok': False, 'message': 'Password muy corto'}), 400
		with db.engine.begin() as conn:
			conn.execute(text("SET LOCK_TIMEOUT 5000;"))
			cols = conn.execute(text("""
				SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
				WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='CierreSucursales_Control_Accesos_Web'
			""")).fetchall()
			colset = {c[0] for c in cols}
			base_cols = ["Nombre","Apellido Paterno","Apellido Materno","Usuario","Password","Departamento","Nivel Acceso","Correo"]
			base_vals = [":n",":ap",":am",":u",":p","'SISTEMAS'","2",":c"]
			params = { 'n':nombre,'ap':ap_pat,'am':ap_mat,'u':usuario,'c':correo }
			if password_is_binary():
				use_salt = 'PasswordSalt' in colset
				digest, salt = make_db_digest(password, use_salt=use_salt)
				params['p'] = digest
				if 'PasswordSalt' in colset:
					base_cols.append('PasswordSalt'); base_vals.append(':s'); params['s'] = salt
				if 'PasswordLastChanged' in colset:
					base_cols.append('PasswordLastChanged'); base_vals.append('GETDATE()')
				if 'IsLegacyPassword' in colset:
					base_cols.append('IsLegacyPassword'); base_vals.append('0')
			else:
				hash_pw = generate_password_hash(password)
				params['p'] = prepare_pw_value(hash_pw)
				if 'PasswordSalt' in colset:
					base_cols.append('PasswordSalt'); base_vals.append('NULL')
				if 'PasswordLastChanged' in colset:
					base_cols.append('PasswordLastChanged'); base_vals.append('GETDATE()')
				if 'IsLegacyPassword' in colset:
					base_cols.append('IsLegacyPassword'); base_vals.append('0')
			if 'PasswordLastChanged' in colset:
				base_cols.append('PasswordLastChanged'); base_vals.append('GETDATE()')
			if 'IsLegacyPassword' in colset:
				base_cols.append('IsLegacyPassword'); base_vals.append('0')
			if 'PasswordSalt' in colset:
				# Already handled above when appropriate
				pass
			cols_sql = ",".join(f"[{c}]" for c in base_cols)
			vals_sql = ",".join(base_vals)
			conn.execute(text(f"INSERT INTO [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] ({cols_sql}) VALUES ({vals_sql})"), params)
		return jsonify({'ok': True, 'message': 'Admin creado'})
	except Exception as e:
		return jsonify({'ok': False, 'message': str(e)}), 500

# --- Página alterna para migrar contraseñas desde la web ---
@app.route('/migrar_passwords', methods=['GET'])
def migrar_passwords_view():
	if not has_migration_access(request):
		flash('No autorizado', 'danger')
		return redirect(url_for('login'))
	return render_template('migrar_passwords.html', token_provided=bool(request.args.get('token')))

@app.route('/migrar_passwords', methods=['POST'])
def migrar_passwords_run():
	if not has_migration_access(request):
		return jsonify({'ok': False, 'message':'No autorizado'}), 403
	mode = request.form.get('mode', 'dry')  # dry | apply
	reset_strategy = request.form.get('reset_strategy', 'random')  # random | fixed
	fixed_temp = (request.form.get('fixed_temp') or '').strip()
	results = []
	rows_changed = 0

	with db.engine.begin() as conn:
		binary_pw = password_is_binary()
		if binary_pw:
			res = conn.execute(text("""
				SELECT id,[Usuario],[Correo],[Password],[PasswordSalt]
				FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
			"""))
		else:
			res = conn.execute(text("""
				SELECT id,[Usuario],[Correo],CAST([Password] AS NVARCHAR(256)) AS Password
				FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
			"""))
		cols = get_table_columns()
		for r in res:
			if binary_pw:
				digest = r.Password
				salt = r.PasswordSalt if hasattr(r, 'PasswordSalt') else None
				# If already 32-byte digest, skip
				if isinstance(digest, (bytes, bytearray)) and len(digest) == 32:
					action = 'already_hashed'; temp = ''
					# nothing to update
				else:
					# Need to create a temp and set digest+salt
					action='reset_temp'; temp = fixed_temp if (reset_strategy=='fixed' and fixed_temp) else gen_temp_password()
					use_salt = 'PasswordSalt' in cols
					nd, ns = make_db_digest(temp, use_salt=use_salt)
					if mode=='apply':
						upd = "UPDATE [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] SET [Password]=:pw"
						params = {'pw': nd, 'id': int(r.id)}
						if 'PasswordSalt' in cols:
							upd += ", [PasswordSalt]=:salt"; params['salt'] = ns
						if 'PasswordLastChanged' in cols:
							upd += ", [PasswordLastChanged]=GETDATE()"
						if 'IsLegacyPassword' in cols:
							upd += ", [IsLegacyPassword]=0"
						upd += " WHERE id=:id"
						conn.execute(text(upd), params)
						rows_changed += 1
			else:
				pw = normalize_pw(r.Password)
				action = 'skip'; new_hash=None; temp=''
				if not pw:
					action='reset_temp'; temp = fixed_temp if (reset_strategy=='fixed' and fixed_temp) else gen_temp_password()
					new_hash = generate_password_hash(temp)
				elif is_werkzeug_hash(pw):
					action='already_hashed'
				elif is_sha256_hex(pw):
					action='reset_temp'; temp = fixed_temp if (reset_strategy=='fixed' and fixed_temp) else gen_temp_password()
					new_hash = generate_password_hash(temp)
				else:
					action='hashed_plaintext'; new_hash = generate_password_hash(pw)

				if mode=='apply' and new_hash:
					conn.execute(text("UPDATE [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] SET [Password]=:pw WHERE id=:id"), {'pw':prepare_pw_value(new_hash),'id':int(r.id)})
					rows_changed += 1

			if action != 'already_hashed':
				results.append({'id':r.id,'usuario':r.Usuario,'correo':r.Correo,'action':action,'temp_password':temp})

	# Guardar CSV en /uploads para descarga rápida
	csv_name = f"migrated_passwords_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
	csv_path = os.path.join('uploads', csv_name)
	os.makedirs('uploads', exist_ok=True)
	with open(csv_path, 'w', newline='', encoding='utf-8') as f:
		w = csv.DictWriter(f, fieldnames=['id','usuario','correo','action','temp_password'])
		w.writeheader(); w.writerows(results)

	return jsonify({'ok': True, 'mode': mode, 'rows_changed': rows_changed, 'csv': url_for('descargar', filename=csv_name)})

def send_notification_email(ceco, departamento):
	try:
		conn = db.engine.connect()
		query_contacts = text("""
			SELECT distinct
				cs4.[Correo 1] as correo1, cs4.[Correo 2] as correo2, cs4.[Correo 3] as correo3,
				cs4.[Correo 4] as correo4, cs4.[Correo 5] as correo5,
				csg.[Seguridad1] as seguridad1, csg.[Seguridad2] as seguridad2, csg.[Seguridad3] as seguridad3,
				csg.[Gerente1] as gerente1, csg.[Gerente2] as gerente2, csg.[Gerente3] as gerente3
			FROM [DBBI].[dbo].[CierreSucursales4] cs4
			CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] csg
			WHERE cs4.[Ceco] = :ceco AND cs4.[Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
		""")
		result = conn.execute(query_contacts, {"ceco": ceco, "departamento": departamento}).fetchone()
		if not result:
			return {"error": f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}"}
		if not isinstance(result, dict):
			result = dict(result._mapping)
		query_assets = text("""
			SELECT distinct [Departamento],[Act. Fijo],[Clase],[Denominacion del activo fijo],[Orden],[Ceco],[Correo 1],[Nivel Correo 1],
				   [Correo 2],[Nivel Correo 2],[Correo 3],[Nivel Correo 3],[Correo 4],[Nivel Correo 4],[Correo 5],[Nivel Correo 5],[Farmacia],[FechaIni]
			FROM [DBBI].[dbo].[CierreSucursales4]
			WHERE [Ceco] = :ceco AND [Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
		""")
		assets = conn.execute(query_assets, {"ceco": ceco, "departamento": departamento}).fetchall()
		if not assets:
			return {"error": f"No se encontraron activos para CECO: {ceco}, Departamento: {departamento}"}
		to_emails, cc_emails = [], []
		for k in ["correo1", "correo2", "correo3"]:
			if result.get(k) and result[k] not in ("None", None):
				to_emails.append(result[k])
		for k in ["correo4", "correo5", "seguridad1", "seguridad2", "seguridad3", "gerente1", "gerente2", "gerente3"]:
			if result.get(k) and result[k] not in ("None", None):
				cc_emails.append(result[k])
		if not to_emails:
			return {"error": "No se encontraron destinatarios principales."}
		html_table = ["<table border='1' cellpadding='5' cellspacing='0'><tr><th>Departamento</th><th>Act. Fijo</th><th>Clase</th><th>Denominacion</th><th>Orden</th><th>CECO</th><th>Farmacia</th><th>Fecha</th></tr>"]
		for row in assets:
			rd = dict(row._mapping) if hasattr(row, '_mapping') else row
			html_table.append(f"<tr><td>{rd.get('Departamento','')}</td><td>{rd.get('Act. Fijo','')}</td><td>{rd.get('Clase','')}</td><td>{rd.get('Denominacion del activo fijo','')}</td><td>{rd.get('Orden','')}</td><td>{rd.get('Ceco','')}</td><td>{rd.get('Farmacia','')}</td><td>{rd.get('FechaIni','')}</td></tr>")
		html_table.append("</table>")
		msg = MIMEMultipart()
		msg['From'] = 'CierreFarmacias@benavides.com.mx'
		msg['To'] = ", ".join(to_emails)
		if cc_emails:
			msg['Cc'] = ", ".join(cc_emails)
		msg['Subject'] = f"Se requiere de su Firma electrónica Solicitante - CECO: {ceco}, Departamento: {departamento}"
		body = f"""<html><body><p>Buen día. Hace unos momentos se subió el archivo para su aprobación.</p>{''.join(html_table)}<p>Ingresar: http://{os.getenv('APP_HOST','localhost')}:{os.getenv('APP_PORT','5020')}/</p></body></html>"""
		msg.attach(MIMEText(body, 'html'))
		try:
			smtp_server = 'casarray.benavides.com.mx'
			server = smtplib.SMTP(smtp_server, 25)
			all_rcpt = to_emails + cc_emails
			server.sendmail(msg['From'], all_rcpt, msg.as_string())
			server.quit()
			return {"success": True, "to": to_emails, "cc": cc_emails, "subject": msg['Subject']}
		except Exception as e:
			return {"error": f"Error al enviar el correo: {e}"}
	except Exception as e:
		return {"error": str(e)}

@app.route('/upload', methods=['GET', 'POST'])
@login_required
@nivel_acceso_required
def upload_file():
	if request.method == 'POST':
		if 'file' not in request.files:
			return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
		file = request.files['file']
		tipo_general = request.form.get('tipo_general')
		if file.filename == '':
			return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
		if not tipo_general:
			return jsonify({'error': 'Debe seleccionar un Tipo General (Baja o Traspaso)'}), 400
		if file and allowed_file(file.filename):
			try:
				df = pd.read_excel(file)
				excel_columns = df.columns.tolist()
				missing_columns = [c for c in EXPECTED_COLUMNS if c not in excel_columns]
				if missing_columns:
					return jsonify({'error': 'Columnas faltantes', 'missing_columns': missing_columns}), 400
				if 'Estatus_General' in df.columns:
					if any(df['Estatus_General'].astype(str).str.strip() == 'Iniciado') and not tipo_general:
						return jsonify({'error': 'Debe seleccionar un Tipo General cuando el Estatus es "Iniciado"'}), 400
				filename_without_ext = os.path.splitext(file.filename)[0]
				current_date = datetime.now().strftime("%d %B %Y")
				df['FileName'] = filename_without_ext
				df['FechaIni'] = current_date
				df['Tipo_General'] = tipo_general
				df['Estatus_General'] = 'Iniciado'
				df['Accion'] = 'Pendiente'
				df.to_sql('CierreSucursales4', db.engine, if_exists='append', index=False, schema='dbo')
				notification_results = []
				for (ceco, departamento), _ in df.groupby(['Ceco', 'Departamento']):
					notification_results.append({'ceco': ceco, 'departamento': departamento, 'result': send_notification_email(ceco, departamento)})
				return jsonify({'success': True, 'message': f'Se insertaron {len(df)} registros', 'notifications': notification_results})
			except Exception as e:
				return jsonify({'error': str(e)}), 500
	return render_template('index_excel_Monse5.html')
# ===================== Rutas restauradas del archivo original =====================

@app.route('/aplicacion')
@login_required
def aplicacion():
	query = text("""SELECT Ceco AS orden_ceco, MAX(FechaIni) AS FechaIni,
		CASE WHEN MAX(FechaFin) IS NOT NULL THEN CONVERT(VARCHAR, MAX(FechaFin), 23) ELSE '-' END AS FechaFin,
		CASE WHEN MAX(FechaFin) IS NOT NULL THEN 'Completado' ELSE MAX(Estatus_General) END AS Estatus_General,
		Tipo_General FROM CierreSucursales4 GROUP BY Ceco, Tipo_General""")
	ordenes = db.session.execute(query).fetchall()
	return render_template('index_3.html', ordenes=ordenes)

@app.route('/detalles/<detalle_id>', methods=['GET','POST'])
@login_required
def detalles_view(detalle_id):
	if request.method == 'POST':
		ActFijo = request.form['ActFijo']
		CecoDestino = request.form['CecoDestino']
		accion = request.form['Accion']
		query = text("""UPDATE CierreSucursales4 SET [Ceco Destino]=:CecoDestino, Accion=:Accion WHERE [Act. Fijo]=:ActFijo""")
		db.session.execute(query, { 'CecoDestino': CecoDestino, 'Accion': accion, 'ActFijo': ActFijo })
		db.session.commit()
		return redirect(url_for('detalles_view', detalle_id=detalle_id))
	query = text("""SELECT DISTINCT Departamento AS departamento, FechaIni, FechaFin, Ceco AS ceco,
		CASE WHEN COUNT(CASE WHEN Accion = 'Baja' THEN 1 END) OVER (PARTITION BY Departamento) > 0 AND
		COUNT(CASE WHEN Accion IS NULL OR Accion = 'Pendiente' THEN 1 END) OVER (PARTITION BY Departamento) > 0 THEN 'Activos Mixto'
		WHEN COUNT(CASE WHEN Accion = 'Baja' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Baja'
		WHEN COUNT(CASE WHEN Accion = 'Pendiente' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Pendientes'
		WHEN COUNT(CASE WHEN Accion = 'Traspaso' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Traspaso'
		ELSE 'Otro' END AS Estatus FROM CierreSucursales4 WHERE Departamento<>'BAJA DIRECTA' AND Ceco = :detalle_id""")
	detalles = db.session.execute(query, { 'detalle_id': detalle_id }).fetchall()
	return render_template('detalles_2.html', detalles=detalles)

@app.route('/borrar/<orden_id>', methods=['POST'])
@login_required
def borrar_orden(orden_id):
	query = text('DELETE FROM CierreSucursales4 WHERE Ceco = :orden_id')
	db.session.execute(query, { 'orden_id': orden_id })
	db.session.commit()
	return redirect(url_for('aplicacion'))

@app.route('/subdetalles/<Departamento>/<Ceco>', methods=['GET','POST'])
@login_required
def subdetalles(Departamento, Ceco):
	try:
		if request.method == 'POST':
			try:
				for activo in request.form.getlist('ActFijo'):
					CecoDestino = request.form.get(f'CecoDestino_{activo}')
					Accion = request.form.get(f'Accion_{activo}')
					CecoDestino = CecoDestino.strip() if CecoDestino else None
					if not Accion:
						raise ValueError('El campo Acción es requerido')
					if Accion == 'Traspaso' and not CecoDestino:
						raise ValueError(f'El CECO destino es requerido para traspasos en el activo {activo}')
					params = { 'Accion': Accion, 'ActFijo': activo, 'Departamento': Departamento, 'Ceco': Ceco }
					if CecoDestino is not None:
						query = text("""UPDATE CierreSucursales4 SET [Ceco Destino]=:CecoDestino, [Accion]=:Accion WHERE [Act. Fijo]=:ActFijo AND [Departamento]=:Departamento AND [Ceco]=:Ceco""")
						params['CecoDestino'] = CecoDestino
					else:
						query = text("""UPDATE CierreSucursales4 SET [Accion]=:Accion, [Ceco Destino]=NULL WHERE [Act. Fijo]=:ActFijo AND [Departamento]=:Departamento AND [Ceco]=:Ceco""")
					db.session.execute(query, params)
				db.session.commit()
				return redirect(url_for('subdetalles', Departamento=Departamento, Ceco=Ceco))
			except ValueError as ve:
				db.session.rollback()
				return render_template('subdetalles_5.html', activos=[], mensaje=str(ve), Departamento=Departamento, Ceco=Ceco)
		query = text("""SELECT [ID],[Departamento],[Act. Fijo],[Denominacion del activo fijo],[Val. Cont.],[Ceco],[Ceco Destino],[Tipo de Activo],[Accion],[Estatus],[Operativo],[Clase],[Fe. Capit.],[Orden],[FirmaSolicitante] FROM CierreSucursales4 WHERE Departamento = :Departamento and Departamento<>'BAJA DIRECTA' AND Ceco=:Ceco ORDER BY [ID]""")
		activos = db.session.execute(query,{ 'Departamento': Departamento, 'Ceco': Ceco }).fetchall()
		if not activos:
			return render_template('subdetalles_5.html', activos=[], mensaje=f'No se encontraron registros para el departamento {Departamento} y CECO {Ceco}.', Departamento=Departamento, Ceco=Ceco)
		return render_template('subdetalles_5.html', activos=activos, mensaje='', Departamento=Departamento, Ceco=Ceco)
	except Exception as e:
		db.session.rollback()
		return render_template('subdetalles_5.html', activos=[], mensaje='Ocurrió un error al procesar su solicitud.', Departamento=Departamento, Ceco=Ceco)

@app.route('/activos/<activo_id>', methods=['GET','POST'])
@login_required
def activos_view(activo_id):
	if request.method == 'POST':
		Operativo = request.form['Operativo']
		CecoDestino = request.form['CecoDestino']
		Accion = request.form['Accion']
		Observaciones = request.form['Observaciones']
		query = text("""UPDATE CierreSucursales4 SET Operativo=:Operativo,[Ceco Destino]=:CecoDestino,Accion=:Accion,Observaciones=:Observaciones WHERE [Act. Fijo]=:ActFijo""")
		db.session.execute(query,{ 'Operativo':Operativo,'CecoDestino':CecoDestino,'Accion':Accion,'Observaciones':Observaciones,'ActFijo':activo_id })
		db.session.commit()
		return redirect(url_for('activos_view', activo_id=activo_id))
	query = text('SELECT * FROM CierreSucursales4 WHERE [Act. Fijo]=:activo_id')
	activo = db.session.execute(query,{ 'activo_id': activo_id}).fetchone()
	if not activo:
		return f'No se encontró el activo con ID: {activo_id}.', 404
	return render_template('activos_4.html', activos=[activo])

@app.route('/adjuntos/<departamento>/<ceco>')
@login_required
def adjuntos(departamento, ceco):
	try:
		current_user_email = session.get('email')
		query = text("""SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path FROM [DBBI].[dbo].[CierreSucursales4] WHERE [Ceco]=:ceco AND Departamento=:departamento""")
		signature_query = text("""SELECT distinct c.[Correo 1], c.[Correo 2], c.[Correo 3], c.[Correo 4], c.[Correo 5], g.[Seguridad1], g.[Seguridad2], g.[Seguridad3], g.[Gerente1], g.[Gerente2], g.[Gerente3], c.[FirmaSolicitante],c.[DetallesFirmaSolicitante], c.[FirmaDepartamento], c.[DetallesFirmaDepartamento], c.[FirmaSeguridad],c.[DetallesFirmaSeguridad],c.[FirmaGerente],c.[DetallesFirmaGerente] FROM [DBBI].[dbo].[CierreSucursales4] c CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] g WHERE c.[Ceco]=:ceco AND c.[Departamento]=:departamento""")
		user_query = text("""SELECT distinct [Nombre],[Apellido Paterno],[Apellido Materno],[Correo],[Departamento] FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] WHERE [Correo]=:email""")
		with db.engine.connect() as connection:
			resultados = connection.execute(query,{ 'ceco': ceco, 'departamento': departamento}).fetchall()
			signature_data = connection.execute(signature_query,{ 'ceco': ceco,'departamento': departamento}).fetchone()
			user_data = connection.execute(user_query,{ 'email': current_user_email}).fetchone()
		archivos = []
		for fila in resultados:
			if fila[0]:
				folder_path = fila[0].strip()
				if os.path.exists(folder_path) and os.path.isdir(folder_path):
					for file_name in os.listdir(folder_path):
						if os.path.isfile(os.path.join(folder_path, file_name)):
							archivos.append(file_name)
		# Inicialización variables de firma
		correo1=correo2=correo3=correo4=correo5=''
		seguridad1=seguridad2=seguridad3=''
		gerente1=gerente2=gerente3=''
		firma_solicitante=firma_departamento=firma_seguridad=firma_gerente=None
		DetallesFirmaDepartamento=DetallesFirmaSolicitante=DetallesfirmaSeguridad=DetallesfirmaGerente=''
		can_sign_as_solicitante=can_sign_as_departamento=can_sign_as_seguridad=can_sign_as_gerente=False
		if signature_data and current_user_email:
			vals = [signature_data[i] if i < len(signature_data) else None for i in range(19)]
			(correo1,correo2,correo3,correo4,correo5,seguridad1,seguridad2,seguridad3,gerente1,gerente2,gerente3,
			 firma_solicitante,DetallesFirmaSolicitante,firma_departamento,DetallesFirmaDepartamento,
			 firma_seguridad,DetallesfirmaSeguridad,firma_gerente,DetallesfirmaGerente) = vals
			# normalizar
			def norm(v): return v.lower().strip() if v else ''
			current_user_email = norm(current_user_email)
			correo1,correo2,correo3,correo4,correo5 = map(norm,[correo1,correo2,correo3,correo4,correo5])
			seguridad1,seguridad2,seguridad3 = map(norm,[seguridad1,seguridad2,seguridad3])
			gerente1,gerente2,gerente3 = map(norm,[gerente1,gerente2,gerente3])
			if (current_user_email in [correo1,correo2,correo3]) and firma_solicitante != 'Verdadero':
				can_sign_as_solicitante = True
			if (current_user_email in [correo4,correo5]) and firma_departamento != 'Verdadero' and firma_solicitante == 'Verdadero':
				can_sign_as_departamento = True
			if (current_user_email in [seguridad1,seguridad2,seguridad3]) and firma_seguridad != 'Verdadero' and firma_solicitante == 'Verdadero' and firma_departamento == 'Verdadero':
				can_sign_as_seguridad = True
			if (current_user_email in [gerente1,gerente2,gerente3]) and firma_gerente != 'Verdadero' and firma_solicitante == 'Verdadero' and firma_departamento == 'Verdadero' and firma_seguridad == 'Verdadero':
				can_sign_as_gerente = True
		user_full_name = ''
		if user_data:
			user_full_name = f"{user_data[0] or ''} {user_data[1] or ''} {user_data[2] or ''}"
		return render_template('Adjuntos_4.html', archivos=archivos, departamento=departamento, ceco=ceco,
			can_sign_as_solicitante=can_sign_as_solicitante, can_sign_as_departamento=can_sign_as_departamento,
			can_sign_as_seguridad=can_sign_as_seguridad, can_sign_as_gerente=can_sign_as_gerente,
			user_full_name=user_full_name, correo1=correo1, correo2=correo2, correo3=correo3, correo4=correo4, correo5=correo5,
			seguridad1=seguridad1, seguridad2=seguridad2, seguridad3=seguridad3, gerente1=gerente1, gerente2=gerente2, gerente3=gerente3,
			firma_solicitante=firma_solicitante, firma_departamento=firma_departamento, firma_seguridad=firma_seguridad, firma_gerente=firma_gerente,
			DetallesFirmaDepartamento=DetallesFirmaDepartamento, DetallesFirmaSolicitante=DetallesFirmaSolicitante,
			DetallesfirmaSeguridad=DetallesfirmaSeguridad, DetallesfirmaGerente=DetallesfirmaGerente)
	except Exception as e:
		app.logger.error(f'Error en adjuntos: {e}')
		return jsonify({'error': str(e)}), 500

@app.route('/guardar_firmas/<departamento>/<ceco>', methods=['POST'])
@login_required
def guardar_firmas(departamento, ceco):
	try:
		current_user_email = session.get('email')
		if not current_user_email:
			return jsonify({'error':'Usuario no autenticado'}), 401
		solicitante_firma = request.form.get('solicitante')
		departamento_firma = request.form.get('departamento')
		seguridad_firma = request.form.get('seguridad')
		gerente_firma = request.form.get('gerente')
		user_query = text("""SELECT [Nombre],[Apellido Paterno],[Apellido Materno] FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web] WHERE [Correo]=:email""")
		check_query = text("""SELECT distinct c.[Correo 1], c.[Correo 2], c.[Correo 3], c.[Correo 4], c.[Correo 5], g.[Seguridad1], g.[Seguridad2], g.[Seguridad3], g.[Gerente1], g.[Gerente2], g.[Gerente3], c.[FirmaSolicitante], c.[DetallesFirmaSolicitante], c.[FirmaDepartamento], c.[DetallesFirmaDepartamento], c.[FirmaSeguridad], c.[DetallesFirmaSeguridad], c.[FirmaGerente], c.[DetallesFirmaGerente] FROM [DBBI].[dbo].[CierreSucursales4] c CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] g WHERE c.[Ceco]=:ceco AND c.[Departamento]=:departamento""")
		with db.engine.connect() as connection:
			user_result = connection.execute(user_query,{ 'email': current_user_email}).fetchone()
			check_result = connection.execute(check_query,{ 'ceco': ceco,'departamento': departamento}).fetchone()
		if not user_result or not check_result:
			return jsonify({'error':'Registro no encontrado'}),404
		(nombre,ap_pat,ap_mat) = user_result
		(correo1,correo2,correo3,correo4,correo5,seguridad1,seguridad2,seguridad3,gerente1,gerente2,gerente3,
		 firma_solicitante_actual,det_solic,firma_departamento_actual,det_depto,firma_seguridad_actual,det_seg,firma_gerente_actual,det_ger)=check_result
		def norm(v): return v.lower().strip() if v else ''
		ue = norm(current_user_email)
		correo1,correo2,correo3,correo4,correo5 = map(norm,[correo1,correo2,correo3,correo4,correo5])
		seguridad1,seguridad2,seguridad3 = map(norm,[seguridad1,seguridad2,seguridad3])
		gerente1,gerente2,gerente3 = map(norm,[gerente1,gerente2,gerente3])
		update_parts=[]; update_params={'ceco': ceco,'departamento': departamento}
		fecha_actual = date.today().strftime('%Y-%m-%d')
		full_name = f"{nombre} {ap_pat} {ap_mat} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
		notification_type=None
		can_sign_as_solicitante = (ue in [correo1,correo2,correo3]) and firma_solicitante_actual!='Verdadero'
		val = request.form.get('solicitante','')
		if solicitante_firma and can_sign_as_solicitante:
			update_parts.append('[FirmaSolicitante]=:fs'); update_params['fs']='Verdadero' if val=='si' else 'Falso'
			update_parts.append('[DetallesFirmaSolicitante]=:dfs'); update_params['dfs']=full_name
			if val=='si': notification_type='solicitante_to_departamento'
		can_sign_as_departamento = (ue in [correo4,correo5]) and firma_departamento_actual!='Verdadero' and firma_solicitante_actual=='Verdadero'
		vald = request.form.get('departamento','')
		if departamento_firma and can_sign_as_departamento:
			update_parts.append('[FirmaDepartamento]=:fd'); update_params['fd']='Verdadero' if vald=='si' else 'Falso'
			update_parts.append('[DetallesFirmaDepartamento]=:dfd'); update_params['dfd']=full_name
			if vald=='si': notification_type='departamento_to_seguridad'
		can_sign_as_seguridad = (ue in [seguridad1,seguridad2,seguridad3]) and firma_seguridad_actual!='Verdadero' and firma_departamento_actual=='Verdadero' and firma_solicitante_actual=='Verdadero'
		vals = request.form.get('seguridad','')
		if seguridad_firma and can_sign_as_seguridad:
			update_parts.append('[FirmaSeguridad]=:fseg'); update_params['fseg']='Verdadero' if vals=='si' else 'Falso'
			update_parts.append('[DetallesFirmaSeguridad]=:dfseg'); update_params['dfseg']=full_name
			if vals=='si': notification_type='seguridad_to_gerencia'
		can_sign_as_gerente = (ue in [gerente1,gerente2,gerente3]) and firma_gerente_actual!='Verdadero' and firma_departamento_actual=='Verdadero' and firma_solicitante_actual=='Verdadero' and firma_seguridad_actual=='Verdadero'
		valg = request.form.get('gerente','')
		if gerente_firma and can_sign_as_gerente:
			update_parts.append('[FirmaGerente]=:fg'); update_params['fg']='Verdadero' if valg=='si' else 'Falso'
			update_parts.append('[DetallesFirmaGerente]=:dfg'); update_params['dfg']=full_name
			update_parts.append('[FechaFin]=:ff'); update_params['ff']=fecha_actual
		if update_parts:
			upd = text(f"UPDATE [DBBI].[dbo].[CierreSucursales4] SET {', '.join(update_parts)} WHERE [Ceco]=:ceco AND Departamento=:departamento")
			with db.engine.begin() as connection:
				connection.execute(upd, update_params)
			flash('Firmas guardadas correctamente','success')
			if notification_type:
				res = send_signature_notification2(ceco, departamento, notification_type)
				if 'error' in res:
					flash('Error al enviar notificación','warning')
		else:
			flash('No se realizaron cambios en las firmas','warning')
		return redirect(url_for('adjuntos', departamento=departamento, ceco=ceco))
	except Exception as e:
		app.logger.error(f'Error en guardar_firmas: {e}')
		return jsonify({'error': str(e)}),500

def send_signature_notification2(ceco, departamento, notification_type):
	try:
		conn = db.engine.connect()
		query_contacts = text("""SELECT distinct cs4.[Correo 1] as correo1, cs4.[Correo 2] as correo2, cs4.[Correo 3] as correo3, cs4.[Correo 4] as correo4, cs4.[Correo 5] as correo5, csg.[Seguridad1] as seguridad1, csg.[Seguridad2] as seguridad2, csg.[Seguridad3] as seguridad3, csg.[Gerente1] as gerente1, csg.[Gerente2] as gerente2, csg.[Gerente3] as gerente3 FROM [DBBI].[dbo].[CierreSucursales4] cs4 CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] csg WHERE cs4.[Ceco]=:ceco AND cs4.[Departamento]=:departamento and Departamento<>'BAJA DIRECTA'""")
		result_contacts = conn.execute(query_contacts,{ 'ceco': ceco,'departamento': departamento}).fetchone()
		if not result_contacts:
			return {'error':'Sin contactos'}
		if not isinstance(result_contacts, dict):
			result_contacts = dict(result_contacts._mapping)
		query_assets = text("""SELECT distinct [Departamento],[Act. Fijo],[Clase],[Denominacion del activo fijo],[Orden],[Ceco],[Farmacia],[FechaIni] FROM [DBBI].[dbo].[CierreSucursales4] WHERE [Ceco]=:ceco AND [Departamento]=:departamento and Departamento<>'BAJA DIRECTA'""")
		assets = conn.execute(query_assets,{ 'ceco': ceco,'departamento': departamento}).fetchall()
		if not assets:
			return {'error':'Sin activos'}
		to_emails=[]; cc_emails=[]; subject_prefix=''
		if notification_type=='solicitante_to_departamento':
			subject_prefix='Se requiere de su Firma electrónica Departamento'
			for k in ['correo4','correo5']:
				if result_contacts.get(k) and result_contacts[k] not in ('None',None): to_emails.append(result_contacts[k])
			for k in ['correo1','correo2','correo3','seguridad1','seguridad2','seguridad3','gerente1','gerente2','gerente3']:
				if result_contacts.get(k) and result_contacts[k] not in ('None',None): cc_emails.append(result_contacts[k])
		elif notification_type=='departamento_to_seguridad':
			subject_prefix='Se requiere de su Firma electrónica Seguridad'
			for k in ['seguridad1','seguridad2','seguridad3']:
				if result_contacts.get(k) and result_contacts[k] not in ('None',None): to_emails.append(result_contacts[k])
			for k in ['correo1','correo2','correo3','correo4','correo5','gerente1','gerente2','gerente3']:
				if result_contacts.get(k) and result_contacts[k] not in ('None',None): cc_emails.append(result_contacts[k])
		elif notification_type=='seguridad_to_gerencia':
			subject_prefix='Se requiere de su Firma electrónica Gerencia'
			for k in ['gerente1','gerente2','gerente3']:
				if result_contacts.get(k) and result_contacts[k] not in ('None',None): to_emails.append(result_contacts[k])
			for k in ['correo1','correo2','correo3','correo4','correo5','seguridad1','seguridad2','seguridad3']:
				if result_contacts.get(k) and result_contacts[k] not in ('None',None): cc_emails.append(result_contacts[k])
		if not to_emails:
			return {'error':'Sin destinatarios principales'}
		html_table=["<table border='1' cellpadding='5' cellspacing='0'><tr><th>Departamento</th><th>Act. Fijo</th><th>Clase</th><th>Denominacion</th><th>Orden</th><th>CECO</th><th>Farmacia</th><th>Fecha</th></tr>"]
		for row in assets:
			rd = dict(row._mapping) if hasattr(row,'_mapping') else row
			html_table.append(f"<tr><td>{rd.get('Departamento','')}</td><td>{rd.get('Act. Fijo','')}</td><td>{rd.get('Clase','')}</td><td>{rd.get('Denominacion del activo fijo','')}</td><td>{rd.get('Orden','')}</td><td>{rd.get('Ceco','')}</td><td>{rd.get('Farmacia','')}</td><td>{rd.get('FechaIni','')}</td></tr>")
		html_table.append('</table>')
		msg = MIMEMultipart(); msg['From']='CierreFarmacias@benavides.com.mx'; msg['To']=', '.join(to_emails)
		if cc_emails: msg['Cc'] = ', '.join(cc_emails)
		msg['Subject']= f"{subject_prefix} - CECO: {ceco}, Departamento: {departamento}"
		body = f"""<html><body><p>Buen día. Se requiere su firma electrónica en el sistema.</p>{''.join(html_table)}<p>Favor de proceder: http://{os.getenv('APP_HOST','localhost')}:{os.getenv('APP_PORT','5020')}/</p></body></html>"""
		msg.attach(MIMEText(body,'html'))
		try:
			server = smtplib.SMTP('casarray.benavides.com.mx',25)
			all_rcpt = to_emails + cc_emails
			server.sendmail(msg['From'], all_rcpt, msg.as_string())
			server.quit()
			return {'success':True,'to':to_emails,'cc':cc_emails,'subject':msg['Subject'],'notification_type':notification_type}
		except Exception as e:
			return {'error': f'Error al enviar correo: {e}'}
	except Exception as e:
		return {'error': str(e)}

# ================== Rutas de listados (ordenes / activos / subordenes) restauradas ==================
@app.route('/ordenes')
@login_required
@nivel_acceso_required
def ordenes():
	try:
		query = text("""SELECT distinct [ID],[FileName],[Tipo],[FechaIni],[FechaFin],[Estatus],[Farmacia],[Domicilio],[Ciudad],[Estado],[GerenteOP],[Director] FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA' ORDER BY [ID] DESC""")
		with db.engine.connect() as conn:
			results = conn.execute(query).fetchall()
		cols = ['ID','FileName','Tipo','FechaIni','FechaFin','Estatus','Farmacia','Domicilio','Ciudad','Estado','GerenteOP','Director']
		data = [dict(zip(cols,row)) for row in results]
		return render_template('ordenes.html', data=data)
	except Exception as e:
		flash(f'Error al cargar los datos: {e}','danger'); return redirect(url_for('dashboard'))

@app.route('/activos')
@login_required
@nivel_acceso_required
def activos():
	try:
		query = text("""SELECT [ID],[Departamento],[Soc.] as Soc,[Act. Fijo] as ActFijo,[Clase],[Fe. Capit.] as FeCapit,[Denominacion del activo fijo] as DenominacionActivoFijo,[Val. Cont.] as ValCont,[Mon.] as Mon,[Orden],[Ceco],[Ceco Destino] as CecoDestino,[Tipo de Activo] as TipoActivo,[Observaciones],[Operativo],[Accion],[Unidades],[PrecioUnitario] FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA' ORDER BY [ID] DESC""")
		with db.engine.connect() as conn:
			results = conn.execute(query).fetchall()
		cols = ['ID','Departamento','Soc','ActFijo','Clase','FeCapit','DenominacionActivoFijo','ValCont','Mon','Orden','Ceco','CecoDestino','TipoActivo','Observaciones','Operativo','Accion','Unidades','PrecioUnitario']
		data = [dict(zip(cols,row)) for row in results]
		return render_template('activos.html', data=data)
	except Exception as e:
		flash(f'Error al cargar los datos: {e}','danger'); return redirect(url_for('dashboard'))

@app.route('/subordenes')
@login_required
@nivel_acceso_required
def subordenes():
	try:
		query = text("""SELECT [ID],[Departamento],[Ceco],[FechaIni],[FechaFin],[Estatus],[Correo 1] as Correo1,[Nivel Correo 1] as NivelCorreo1,[Correo 2] as Correo2,[Nivel Correo 2] as NivelCorreo2,[Correo 3] as Correo3,[Nivel Correo 3] as NivelCorreo3,[Correo 4] as Correo4,[Nivel Correo 4] as NivelCorreo4,[Correo 5] as Correo5,[Nivel Correo 5] as NivelCorreo5,[FirmaSolicitante],[DetallesFirmaSolicitante],[FirmaDepartamento],[DetallesFirmaDepartamento],[FirmaSeguridad],[DetallesFirmaSeguridad],[FirmaGerente],[DetallesFirmaGerente],[Tipo] FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA' ORDER BY [ID] DESC""")
		with db.engine.connect() as conn:
			results = conn.execute(query).fetchall()
		cols = ['ID','Departamento','Ceco','FechaIni','FechaFin','Estatus','Correo1','NivelCorreo1','Correo2','NivelCorreo2','Correo3','NivelCorreo3','Correo4','NivelCorreo4','Correo5','NivelCorreo5','FirmaSolicitante','DetallesFirmaSolicitante','FirmaDepartamento','DetallesFirmaDepartamento','FirmaSeguridad','DetallesFirmaSeguridad','FirmaGerente','DetallesFirmaGerente','Tipo']
		data = [dict(zip(cols,row)) for row in results]
		return render_template('subordenes2.html', data=data)
	except Exception as e:
		flash(f'Error al cargar los datos: {e}','danger'); return redirect(url_for('dashboard'))

@app.route('/actualizar_subordenes', methods=['POST'])
@login_required
@nivel_acceso_required
def actualizar_subordenes():
	try:
		data = request.get_json(); suborden_id = data.get('id'); updates = data.get('updates', {})
		if not suborden_id or not updates:
			return jsonify({'error':'Datos inválidos'}),400
		update_columns=[]; update_values=[]
		for column,value in updates.items():
			db_column = f'[{column.replace("Correo","Correo ")}]'
			update_columns.append(f'{db_column} = :val_{column}')
			update_values.append((f'val_{column}', value))
		if update_columns:
			update_query = text(f"UPDATE [DBBI].[dbo].[CierreSucursales4] SET {', '.join(update_columns)} WHERE [ID] = :id")
			update_values.append(('id', suborden_id))
			with db.engine.connect() as conn:
				conn.execute(update_query, dict(update_values)); conn.commit()
			return jsonify({'message':'Actualización exitosa'}),200
		return jsonify({'error':'No hay actualizaciones'}),400
	except Exception as e:
		return jsonify({'error': f'Error al actualizar: {e}'}),500

@app.route('/send_notifications', methods=['POST'])
@login_required
@nivel_acceso_required
def send_notifications():
	try:
		data = request.json; ceco = data.get('ceco'); departamento = data.get('departamento')
		if not ceco or not departamento:
			return jsonify({'error':'Debe proporcionar CECO y Departamento'}),400
		result = send_notification_email(ceco, departamento)
		if 'error' in result:
			return jsonify({'error': result['error']}),400
		return jsonify({'success':True,'notification': result})
	except Exception as e:
		return jsonify({'error': str(e)}),500

@app.route('/eliminar_archivos/<departamento>/<ceco>', methods=['POST'])
@login_required
def eliminar_archivos(departamento, ceco):
	try:
		files_to_delete = request.json.get('files', [])
		query = text("""SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path FROM [DBBI].[dbo].[CierreSucursales4] WHERE [Ceco]=:ceco AND Departamento=:departamento""")
		with db.engine.connect() as connection:
			resultados = connection.execute(query,{ 'ceco': ceco,'departamento': departamento}).fetchall()
		deleted_files=[]
		if resultados and resultados[0][0]:
			folder_path = resultados[0][0].strip()
			for filename in files_to_delete:
				full_path = os.path.join(folder_path, filename)
				if os.path.commonpath([folder_path, full_path]) == folder_path and os.path.exists(full_path):
					os.remove(full_path); deleted_files.append(filename)
		return jsonify({'success':True,'deleted_files':deleted_files})
	except Exception as e:
		return jsonify({'success':False,'error':str(e)}),500

@app.route('/descargar/<departamento>/<ceco>/<filename>')
@login_required
def descargar(departamento, ceco, filename):
	try:
		query = text("""SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path FROM [DBBI].[dbo].[CierreSucursales4] WHERE [Ceco]=:ceco AND Departamento=:departamento""")
		with db.engine.connect() as connection:
			resultados = connection.execute(query,{ 'ceco': ceco,'departamento': departamento}).fetchall()
		if not resultados:
			return jsonify({'error':'No se encontró la ruta en la base de datos'}),404
		folder_path = os.path.normpath(resultados[0][0].strip())
		if not os.path.exists(folder_path):
			return jsonify({'error': f'La ruta no existe: {folder_path}'}),404
		return send_from_directory(folder_path, filename, as_attachment=True)
	except Exception as e:
		return jsonify({'error': str(e)}),500

@app.route('/subir/<departamento>/<ceco>', methods=['POST'])
@login_required
def subir(departamento, ceco):
        if 'archivo' not in request.files:
                return 'No file part',400
        archivo = request.files['archivo']
        if archivo.filename == '':
                return 'No selected file',400
        filename = secure_filename(archivo.filename)
        if not allowed_file(filename):
                return 'Tipo de archivo no permitido',400
        try:
                query = text("""SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path FROM [DBBI].[dbo].[CierreSucursales4] WHERE [Ceco]=:ceco AND Departamento=:departamento""")
                with db.engine.connect() as connection:
                        resultados = connection.execute(query,{ 'ceco': ceco,'departamento': departamento}).fetchall()
                if not resultados:
                        return 'No se encontró una ruta válida en la base de datos',400
                folder_path = resultados[0][0].strip()
                if not os.path.exists(folder_path): os.makedirs(folder_path)
                archivo.save(os.path.join(folder_path, filename))
                return redirect(url_for('adjuntos', departamento=departamento, ceco=ceco))
        except Exception as e:
                return jsonify({'error': str(e)}),500

@app.route('/PDF/<departamento>/<ceco>', methods=['POST'])
@login_required
def generar_pdf(departamento, ceco):
	try:
		scripts = [
			('P:/CierreFarmacias/Scripts/python.exe','P:/CierreFarmacias/PDF7_Traspaso.py',departamento,ceco),
			('P:/CierreFarmacias/Scripts/python.exe','P:/CierreFarmacias/PDF_BAJA.py',departamento,ceco),
			('P:/CierreFarmacias/Scripts/python.exe','P:/CierreFarmacias/PDF_Tecnico.py',departamento,ceco),
			('P:/CierreFarmacias/Scripts/python.exe','P:/CierreFarmacias/pdf_Recoleccion.py',departamento,ceco)
		]
		for script in scripts:
			result = subprocess.run(script, capture_output=True, text=True)
			if result.returncode != 0: raise Exception(result.stderr)
		return jsonify({'success':True,'message':'PDFs generados correctamente'}),200
	except Exception as e:
		return jsonify({'success':False,'error': str(e)}),500

# ----- Portal de accesos -----
@app.route('/accesos', methods=['GET','POST'])
@login_required
def accesos():
	if request.method == 'POST':
		nombre = request.form.get('nombre'); apellido_paterno = request.form.get('apellido_paterno')
		apellido_materno = request.form.get('apellido_materno'); password = request.form.get('password')
		departamento = request.form.get('departamento'); nivel_acceso = request.form.get('nivel_acceso'); correo = request.form.get('correo')
		usuario = correo.split('@')[0] if correo else ''
		if not all([nombre, apellido_paterno, apellido_materno, password, departamento, nivel_acceso, correo]):
			flash('Todos los campos son obligatorios','danger'); return redirect(url_for('accesos'))
		try:
			conn = db.engine.connect(); usuario_existente = conn.execute(text("SELECT Correo FROM CierreSucursales_Control_Accesos_Web WHERE Correo = :correo"),{'correo': correo}).fetchone(); conn.close()
			if usuario_existente:
				flash('El correo ya está registrado','danger'); return redirect(url_for('accesos'))
		except Exception as e:
			flash(f'Error al verificar correo: {e}','danger'); return redirect(url_for('accesos'))
		try:
			cols = get_table_columns()
			if password_is_binary():
				digest, salt = make_db_digest(password)
				base_cols = ["Nombre","Apellido Paterno","Apellido Materno","Usuario","Password","Departamento","Nivel Acceso","Correo"]
				base_vals_list = [":nombre",":apellido_paterno",":apellido_materno",":usuario",":password",":departamento",":nivel_acceso",":correo"]
				if 'PasswordSalt' in cols:
					base_cols.append('PasswordSalt'); base_vals_list.append(":salt")
				if 'PasswordLastChanged' in cols:
					base_cols.append('PasswordLastChanged'); base_vals_list.append("GETDATE()")
				if 'IsLegacyPassword' in cols:
					base_cols.append('IsLegacyPassword'); base_vals_list.append("0")
				cols_sql = ",".join(f"[{c}]" for c in base_cols)
				vals_sql = ",".join(base_vals_list)
				sql = text(f"INSERT INTO CierreSucursales_Control_Accesos_Web ({cols_sql}) VALUES ({vals_sql})")
				params = { 'nombre': nombre,'apellido_paterno': apellido_paterno,'apellido_materno': apellido_materno,'usuario': usuario,'password': digest,'departamento': departamento,'nivel_acceso': int(nivel_acceso),'correo': correo }
				if 'PasswordSalt' in cols:
					params['salt'] = salt
				conn = db.engine.connect(); conn.execute(sql, params); conn.commit(); conn.close()
			else:
				hashed_pw = generate_password_hash(password)
				sql = text("""INSERT INTO CierreSucursales_Control_Accesos_Web ([Nombre],[Apellido Paterno],[Apellido Materno],[Usuario],[Password],[Departamento],[Nivel Acceso],[Correo]) VALUES (:nombre,:apellido_paterno,:apellido_materno,:usuario,:password,:departamento,:nivel_acceso,:correo)""")
				conn = db.engine.connect(); conn.execute(sql,{ 'nombre': nombre,'apellido_paterno': apellido_paterno,'apellido_materno': apellido_materno,'usuario': usuario,'password': hashed_pw,'departamento': departamento,'nivel_acceso': int(nivel_acceso),'correo': correo}); conn.commit(); conn.close()
			flash('Usuario guardado correctamente','success'); return redirect(url_for('lista_usuarios'))
		except Exception as e:
			flash(f'Error al guardar: {e}','danger'); return redirect(url_for('accesos'))
	return render_template('accesos.html')

@app.route('/usuarios')
@login_required
def lista_usuarios():
	try:
		conn = db.engine.connect(); result = conn.execute(text("""SELECT [id],[Nombre],[Apellido Paterno],[Apellido Materno],[Usuario],[Password],[Departamento],[Nivel Acceso],[Correo] FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]"""))
		usuarios=[]
		for row in result:
			usuarios.append({'id':row[0],'Nombre':row[1],'Apellido_Paterno':row[2],'Apellido_Materno':row[3],'Usuario':row[4],'Password':row[5],'Departamento':row[6],'Nivel_Acceso':row[7],'Correo':row[8]})
		conn.close(); return render_template('usuarios.html', usuarios=usuarios)
	except Exception as e:
		flash(f'Error al cargar usuarios: {e}','danger'); return redirect(url_for('index'))

@app.route('/actualizar_usuario', methods=['POST'])
@login_required
def actualizar_usuario():
	try:
		id = request.form.get('id'); nombre=request.form.get('nombre'); apellido_paterno=request.form.get('apellido_paterno'); apellido_materno=request.form.get('apellido_materno'); password=request.form.get('password'); departamento=request.form.get('departamento'); nivel_acceso=request.form.get('nivel_acceso')
		params = { 'nombre':nombre,'apellido_paterno':apellido_paterno,'apellido_materno':apellido_materno,'departamento':departamento,'nivel_acceso':int(nivel_acceso),'id':int(id) }
		if password:
			cols = get_table_columns()
			if password_is_binary():
				nd, ns = make_db_digest(password)
				upd = "UPDATE CierreSucursales_Control_Accesos_Web SET [Nombre]=:nombre,[Apellido Paterno]=:apellido_paterno,[Apellido Materno]=:apellido_materno,[Password]=:password,[Departamento]=:departamento,[Nivel Acceso]=:nivel_acceso"
				params['password'] = nd
				if 'PasswordSalt' in cols:
					upd += ",[PasswordSalt]=:salt"; params['salt'] = ns
				if 'PasswordLastChanged' in cols:
					upd += ",[PasswordLastChanged]=GETDATE()"
				if 'IsLegacyPassword' in cols:
					upd += ",[IsLegacyPassword]=0"
				upd += " WHERE id=:id"
				sql = text(upd)
			else:
				hashed_pw = generate_password_hash(password)
				sql = text("""UPDATE CierreSucursales_Control_Accesos_Web SET [Nombre]=:nombre,[Apellido Paterno]=:apellido_paterno,[Apellido Materno]=:apellido_materno,[Password]=:password,[Departamento]=:departamento,[Nivel Acceso]=:nivel_acceso WHERE id=:id""")
				params['password'] = prepare_pw_value(hashed_pw)
		else:
			sql = text("""UPDATE CierreSucursales_Control_Accesos_Web SET [Nombre]=:nombre,[Apellido Paterno]=:apellido_paterno,[Apellido Materno]=:apellido_materno,[Departamento]=:departamento,[Nivel Acceso]=:nivel_acceso WHERE id=:id""")
		with db.engine.begin() as conn:
			conn.execute(sql, params)
		return jsonify({'success':True,'message':'Usuario actualizado correctamente'})
	except Exception as e:
		return jsonify({'success':False,'message':f'Error: {e}'}),500

@app.route('/eliminar_usuario', methods=['POST'])
@login_required
def eliminar_usuario():
	try:
		id = request.form.get('id'); sql = text('DELETE FROM CierreSucursales_Control_Accesos_Web WHERE id=:id'); conn = db.engine.connect(); conn.execute(sql,{ 'id': int(id)}); conn.commit(); conn.close(); return jsonify({'success':True,'message':'Usuario eliminado correctamente'})
	except Exception as e:
		return jsonify({'success':False,'message':f'Error: {e}'}),500

@app.route('/data')
def get_data():
	query = text("""SELECT Departamento, SUM(cont) AS cont, Accion FROM (SELECT Departamento, Accion, COUNT(*) AS cont FROM DBBI.dbo.CierreSucursales4 WHERE Departamento <> 'BAJA DIRECTA' GROUP BY Departamento, Accion) AS subquery GROUP BY Departamento, Accion""")
	result = db.session.execute(query)
	data = [["Departamento","Cantidad","Accion"]] + [list(row) for row in result]
	return jsonify(data)

@app.route('/summary')
def get_summary():
	query = text("""SELECT Departamento, SUM(cont) AS total FROM (SELECT Departamento, Accion, COUNT(*) AS cont FROM DBBI.dbo.CierreSucursales4 WHERE Departamento <> 'BAJA DIRECTA' GROUP BY Departamento, Accion) AS subquery GROUP BY Departamento""")
	result = db.session.execute(query)
	data = [["Departamento","Total"]] + [list(row) for row in result]
	return jsonify(data)

@app.route('/lista_Seguridad_Gerencias')
@login_required
def lista_Seguridad_Gerencias():
	try:
		conn = db.engine.connect(); query = text("""SELECT [ID],[Seguridad1],[Seguridad2],[Seguridad3],[Gerente1],[Gerente2],[Gerente3] FROM [DBBI].[dbo].[CierreSucursales_Gerentes] ORDER BY [ID] DESC"""); result = conn.execute(query)
		Seguridad_Gerencias=[]
		for row in result:
			Seguridad_Gerencias.append({'id':row[0],'Seguridad1':row[1],'Seguridad2':row[2],'Seguridad3':row[3],'Gerente1':row[4],'Gerente2':row[5],'Gerente3':row[6]})
		conn.close(); return render_template('lista_Seguridad_Gerencias.html', Seguridad_Gerencias=Seguridad_Gerencias)
	except Exception as e:
		return f'Error en la consulta: {e}',500

@app.route('/actualizar_Seguridad_Gerencia', methods=['POST'])
@login_required
def actualizar_Seguridad_Gerencia():
	try:
		id = request.form['id']; seguridad1=request.form['Seguridad1']; seguridad2=request.form['Seguridad2']; seguridad3=request.form['Seguridad3']; gerente1=request.form['Gerente1']; gerente2=request.form['Gerente2']; gerente3=request.form['Gerente3']
		conn = db.engine.connect(); query = text("""UPDATE [DBBI].[dbo].[CierreSucursales_Gerentes] SET [Seguridad1]=:seg1,[Seguridad2]=:seg2,[Seguridad3]=:seg3,[Gerente1]=:ger1,[Gerente2]=:ger2,[Gerente3]=:ger3 WHERE [ID]=:id"""); conn.execute(query,{ 'seg1':seguridad1,'seg2':seguridad2,'seg3':seguridad3,'ger1':gerente1,'ger2':gerente2,'ger3':gerente3,'id':id}); conn.commit(); conn.close(); return jsonify({'success':True,'message':'Usuario actualizado correctamente'})
	except Exception as e:
		return jsonify({'success':False,'message':f'Error: {e}'}),500

# Presentación / Tour
@app.route('/presentacion')
def mostrar_presentacion():
	pptx_name = 'Manual_CierreFarmacias'
	presentation_dir = os.path.join(app.static_folder,'presentaciones',pptx_name)
	if not os.path.exists(presentation_dir):
		return f'Error: El directorio {presentation_dir} no existe.'
	try:
		image_files = [f for f in os.listdir(presentation_dir) if f.lower().endswith(('.png','.jpg','.jpeg'))]
		image_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]) if '_' in x and x.split('_')[1].split('.')[0].isdigit() else 9999)
		return render_template('presentacion.html', presentacion=pptx_name, imagenes=image_files)
	except Exception as e:
		return f'Error al procesar las imágenes: {e}'

@app.route('/check_files')
def check_files():
	static_dir = app.static_folder; presentaciones_dir = os.path.join(static_dir,'presentaciones')
	result = { 'static_folder': static_dir, 'static_folder_exists': os.path.exists(static_dir), 'presentaciones_dir': presentaciones_dir, 'presentaciones_dir_exists': os.path.exists(presentaciones_dir) }
	if os.path.exists(presentaciones_dir):
		presentation_dirs = os.listdir(presentaciones_dir); result['presentation_dirs']=presentation_dirs
		for pres_dir in presentation_dirs:
			full_pres_dir = os.path.join(presentaciones_dir, pres_dir)
			if os.path.isdir(full_pres_dir): result[f'files_in_{pres_dir}']=os.listdir(full_pres_dir)
	return jsonify(result)

# ================== Fin rutas restauradas ==================

