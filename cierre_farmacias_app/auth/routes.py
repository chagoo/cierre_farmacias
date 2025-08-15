from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import text
from functools import wraps
from ..extensions import db

bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder a esta página', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        query = text("""
        SELECT [Usuario], [Password], [Nivel Acceso], [Nombre], [Apellido Paterno],[Correo]
        FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
        WHERE [Usuario] = :username AND [Password] = :password
        """)

        try:
            with db.engine.connect() as conn:
                result = conn.execute(query, {'username': username, 'password': password}).fetchone()

            if result and int(result[2]) == 2:
                session['user_id'] = result[0]
                session['nombre_completo'] = f"{result[3]} {result[4]}"
                session['nivel_acceso'] = int(result[2])
                session['email'] = result[5]
                return redirect(url_for('auth.dashboard'))
            flash('Usuario o contraseña incorrectos', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/')
def index():
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    if session.get('nivel_acceso') == 2:
        return render_template('dashboard2.html')
    flash('Acceso no autorizado', 'danger')
    return redirect(url_for('auth.login'))
