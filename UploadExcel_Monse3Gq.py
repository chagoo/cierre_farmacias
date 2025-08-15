# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, redirect, url_for,send_from_directory, session, flash
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from functools import wraps
from sqlalchemy import text
import subprocess
from datetime import date 
from flask import redirect, url_for, render_template
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import smtplib
import logging



app = Flask(__name__) 
app.secret_key = 'Te_llore_un_rio'  # Necesaria para las sesiones

# Configuración de la base de datos
DB_SERVER = 'MPWPAS01'
DB_NAME = 'DBBI'
DB_USER = 'AlertDBBI'
DB_PASSWORD = 'P4$9'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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


app.secret_key = 'Te_llore_un_rio'  # Necesario para manejar sesiones

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Consultar la base de datos para verificar las credenciales
        query = text("""
        SELECT [Usuario], [Password], [Nivel Acceso], [Nombre], [Apellido Paterno],[Correo]
        FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
        WHERE [Usuario] = :username AND [Password] = :password
        """)
        
        try:
            # Usar la forma correcta para ejecutar consultas en SQLAlchemy
            with db.engine.connect() as conn:
                result = conn.execute(query, {'username': username, 'password': password}).fetchone()
            
            if result:
                nivel_acceso = int(result[2])  # Convertir a entero
                
                if nivel_acceso == 2:
                    session['user_id'] = result[0]
                    session['nombre_completo'] = f"{result[3]} {result[4]}"
                    session['nivel_acceso'] = nivel_acceso
                    session['email'] = result[5]  # Guardar el correo en la sesión
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
    else:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('login'))


def send_notification_email(ceco, departamento):
    try:
        # Conexión a la base de datos usando el engine existente
        conn = db.engine.connect()
        
        # Consultar los contactos según el CECO y departamento
        query_contacts = text("""
            SELECT distinct
                cs4.[Correo 1] as correo1, 
                cs4.[Correo 2] as correo2, 
                cs4.[Correo 3] as correo3, 
                cs4.[Correo 4] as correo4, 
                cs4.[Correo 5] as correo5,
                csg.[Seguridad1] as seguridad1, 
                csg.[Seguridad2] as seguridad2, 
                csg.[Seguridad3] as seguridad3,
                csg.[Gerente1] as gerente1, 
                csg.[Gerente2] as gerente2, 
                csg.[Gerente3] as gerente3
            FROM [DBBI].[dbo].[CierreSucursales4] cs4
            CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] csg
            WHERE cs4.[Ceco] = :ceco AND cs4.[Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
        """)
        
        # Configurar para obtener resultados como diccionarios
        result = conn.execute(query_contacts, {"ceco": ceco, "departamento": departamento})
        result_contacts = result.fetchone()
        
        if not result_contacts:
            print(f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}")
            return {"error": f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}"}
        
        # Convertir Row a diccionario si es necesario
        if not isinstance(result_contacts, dict):
            result_contacts = dict(result_contacts._mapping)
        
        # Consultar los datos de los activos para incluir en el correo
        query_assets = text("""
            SELECT distinct
                [Departamento],
                [Act. Fijo],
                [Clase],
                [Denominacion del activo fijo],
                [Orden],
                [Ceco],
                [Correo 1],
                [Nivel Correo 1],
                [Correo 2],
                [Nivel Correo 2],
                [Correo 3],
                [Nivel Correo 3],
                [Correo 4],
                [Nivel Correo 4],
                [Correo 5],
                [Nivel Correo 5],
                [Farmacia],
                [FechaIni]
            FROM [DBBI].[dbo].[CierreSucursales4]
            WHERE [Ceco] = :ceco AND [Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
        """)
        
        result_assets = conn.execute(query_assets, {"ceco": ceco, "departamento": departamento}).fetchall()
        
        if not result_assets:
            print(f"No se encontraron activos para CECO: {ceco}, Departamento: {departamento}")
            return {"error": f"No se encontraron activos para CECO: {ceco}, Departamento: {departamento}"}
        
        # Determinar los destinatarios principales según el departamento
        to_emails = []
        cc_emails = []
        
        # Para los destinatarios principales (TO)
        email_keys = ["correo1", "correo2", "correo3"]
        for key in email_keys:
            if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                to_emails.append(result_contacts[key])
        
        # Para los destinatarios en copia (CC)
        cc_keys = ["correo4", "correo5"]
        for key in cc_keys:
            if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                cc_emails.append(result_contacts[key])
        
        # Agregar contactos de seguridad y gerentes al CC
        security_manager_keys = ["seguridad1", "seguridad2", "seguridad3", "gerente1", "gerente2", "gerente3"]
        for key in security_manager_keys:
            if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                cc_emails.append(result_contacts[key])
        
        # Si no hay destinatarios principales, usar los responsables
        if not to_emails:
            print("No se encontraron destinatarios principales. Se requiere implementar lógica para responsables.")
            return {"error": "No se encontraron destinatarios principales. Se requiere implementar lógica para responsables."}
        
        # Crear tabla HTML con los datos de los activos
        html_table = """
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Departamento</th>
                <th>Act. Fijo</th>
                <th>Clase</th>
                <th>Denominacion</th>
                <th>Orden</th>
                <th>CECO</th>
                <th>Farmacia</th>
                <th>Fecha</th>
            </tr>
        """
        
        # Llenar la tabla con los datos - asegúrate que sea acceso por índice o diccionario según el tipo de result_assets
        for row in result_assets:
            # Convertir Row a diccionario si es necesario
            if hasattr(row, '_mapping'):
                row_dict = dict(row._mapping)
            else:
                row_dict = row
                
            html_table += f"""
            <tr>
                <td>{row_dict.get('Departamento', '')}</td>
                <td>{row_dict.get('Act. Fijo', '')}</td>
                <td>{row_dict.get('Clase', '')}</td>
                <td>{row_dict.get('Denominacion del activo fijo', '')}</td>
                <td>{row_dict.get('Orden', '')}</td>
                <td>{row_dict.get('Ceco', '')}</td>
                <td>{row_dict.get('Farmacia', '')}</td>
                <td>{row_dict.get('FechaIni', '')}</td>
            </tr>
            """
        
        html_table += "</table>"
        
        # Configurar el mensaje
        msg = MIMEMultipart()
        msg['From'] = 'CierreFarmacias@benavides.com.mx'
        msg['To'] = ", ".join(to_emails)
        if cc_emails:
            msg['Cc'] = ", ".join(cc_emails)
        
        # Asunto del correo según lo solicitado
        msg['Subject'] = f"Se requiere de su Firma electrónica Solicitante - CECO: {ceco}, Departamento: {departamento}"
        
        # Cuerpo del correo
        body = f"""
        <html>
        <body>
            <p>Buen día. Hace unos momentos se subió el archivo para su aprobación.</p>
            {html_table}
            <p>Favor de proceder con su firma electrónica en esta liga http://10.30.43.103:5020/.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Configuración del servidor SMTP corregida
        smtp_server = 'casarray.benavides.com.mx'
        smtp_port = 25
        smtp_user = 'CierreFarmacias@benavides.com.mx'
        
        # Enviar el correo con mejor logging
        try:
            all_recipients = to_emails + cc_emails
            print(f"Intentando enviar correo a: {', '.join(all_recipients)}")
            print(f"SMTP Server: {smtp_server}:{smtp_port}")
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            print("Conexión al servidor SMTP establecida")
            
            server.sendmail(msg['From'], all_recipients, msg.as_string())
            print(f"Correo enviado exitosamente a: {', '.join(all_recipients)}")
            print(f"Asunto: {msg['Subject']}")
            server.quit()
            print("Conexión al servidor SMTP cerrada")
            
            return {
                "success": True,
                "to": to_emails,
                "cc": cc_emails,
                "subject": msg['Subject']
            }
        except Exception as email_error:
            print(f"Error al enviar el correo: {str(email_error)}")
            return {"error": f"Error al enviar el correo: {str(email_error)}"}
        
    except Exception as e:
        print(f"Error general en send_notification_email: {str(e)}")
        return {"error": str(e)}


# Modificar la función de upload_file para llamar a la función de notificación
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
                # Leer el Excel
                df = pd.read_excel(file)
                
                # Verificar las columnas
                excel_columns = df.columns.tolist()
                missing_columns = [col for col in EXPECTED_COLUMNS if col not in excel_columns]
                
                if missing_columns:
                    return jsonify({
                        'error': 'Las columnas del archivo no coinciden',
                        'missing_columns': missing_columns
                    }), 400
                
                # Validar que si Estatus_General es "Iniciado", se haya seleccionado Tipo_General
                if 'Estatus_General' in df.columns:
                    if any(df['Estatus_General'].astype(str).str.strip() == 'Iniciado') and not tipo_general:
                        return jsonify({'error': 'Debe seleccionar un Tipo General cuando el Estatus es "Iniciado"'}), 400
                
                # Preparar datos adicionales
                filename_without_ext = os.path.splitext(file.filename)[0]
                current_date = datetime.now().strftime("%d %B %Y")
                estatus_general = 'Iniciado'
                Accion = 'Pendiente'
                
                # Agregar columnas adicionales
                df['FileName'] = filename_without_ext
                df['FechaIni'] = current_date
                df['Tipo_General'] = tipo_general
                df['Estatus_General'] = estatus_general
                df['Accion'] = Accion
                
                # Insertar en la base de datos
                df.to_sql('CierreSucursales4', db.engine, if_exists='append', index=False, schema='dbo')
                
                # Enviar notificaciones por correo electrónico
                notification_results = []
                
                # Agrupar por CECO y Departamento para enviar un correo por cada combinación única
                for (ceco, departamento), group in df.groupby(['Ceco', 'Departamento']):
                    result = send_notification_email(ceco, departamento)
                    notification_results.append({
                        'ceco': ceco,
                        'departamento': departamento,
                        'result': result
                    })
                
                return jsonify({
                    'success': True,
                    'message': f'Se insertaron {len(df)} registros exitosamente',
                    'notifications': notification_results
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
    return render_template('index_excel_Monse5.html')

# Nueva ruta específica para enviar notificaciones (opcional)
@app.route('/send_notifications', methods=['POST'])
@login_required
@nivel_acceso_required
def send_notifications():
    try:
        data = request.json
        ceco = data.get('ceco')
        departamento = data.get('departamento')
        
        if not ceco or not departamento:
            return jsonify({'error': 'Debe proporcionar CECO y Departamento'}), 400
        
        result = send_notification_email(ceco, departamento)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'notification': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/ordenes')
@login_required
@nivel_acceso_required
def ordenes():
    try:
        query = text("""
        SELECT distinct [ID], [FileName], [Tipo], [FechaIni], [FechaFin], 
               [Estatus], [Farmacia], [Domicilio], [Ciudad], [Estado], 
               [GerenteOP], [Director]
        FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA'
        ORDER BY [ID] DESC
        """)
        
        with db.engine.connect() as conn:
            results = conn.execute(query).fetchall()
        
        columns = ['ID', 'FileName', 'Tipo', 'FechaIni', 'FechaFin', 
                  'Estatus', 'Farmacia', 'Domicilio', 'Ciudad', 'Estado', 
                  'GerenteOP', 'Director']
        
        data = []
        for row in results:
            data.append(dict(zip(columns, row)))
        
        return render_template('ordenes.html', data=data)
    
    except Exception as e:
        flash(f'Error al cargar los datos: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/activos')
@login_required
@nivel_acceso_required
def activos():
    try:
        query = text("""
        SELECT [ID], [Departamento], [Soc.] as Soc, [Act. Fijo] as ActFijo, 
               [Clase], [Fe. Capit.] as FeCapit, [Denominacion del activo fijo] as DenominacionActivoFijo, 
               [Val. Cont.] as ValCont, [Mon.] as Mon, [Orden], [Ceco], 
               [Ceco Destino] as CecoDestino, [Tipo de Activo] as TipoActivo, 
               [Observaciones], [Operativo], [Accion], [Unidades], [PrecioUnitario]
        FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA'
        ORDER BY [ID] DESC
        """)
        
        with db.engine.connect() as conn:
            results = conn.execute(query).fetchall()
        
        columns = ['ID', 'Departamento', 'Soc', 'ActFijo', 'Clase', 'FeCapit', 
                  'DenominacionActivoFijo', 'ValCont', 'Mon', 'Orden', 'Ceco', 
                  'CecoDestino', 'TipoActivo', 'Observaciones', 'Operativo', 
                  'Accion', 'Unidades', 'PrecioUnitario']
        
        data = []
        for row in results:
            data.append(dict(zip(columns, row)))
        print("Datos obtenidos:", data)  # <-- Agregar esta línea para verificar datos en consola
        
        return render_template('activos.html', data=data)
    
    except Exception as e:
        flash(f'Error al cargar los datos: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/subordenes')
@login_required
@nivel_acceso_required
def subordenes():
    try:
        query = text("""
        SELECT [ID], [Departamento], [Ceco], [FechaIni],  [FechaFin], 
               [Estatus], 
               [Correo 1] as Correo1, [Nivel Correo 1] as NivelCorreo1, 
               [Correo 2] as Correo2, [Nivel Correo 2] as NivelCorreo2, 
               [Correo 3] as Correo3, [Nivel Correo 3] as NivelCorreo3, 
               [Correo 4] as Correo4, [Nivel Correo 4] as NivelCorreo4, 
               [Correo 5] as Correo5, [Nivel Correo 5] as NivelCorreo5, 
               [FirmaSolicitante], [DetallesFirmaSolicitante], 
               [FirmaDepartamento], [DetallesFirmaDepartamento], 
               [FirmaSeguridad], [DetallesFirmaSeguridad], 
               [FirmaGerente], [DetallesFirmaGerente], [Tipo]
        FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA'
        ORDER BY [ID] DESC
        """)

        with db.engine.connect() as conn:
            results = conn.execute(query).fetchall()

        columns = ['ID', 'Departamento', 'Ceco', 'FechaIni', 'FechaFin', 
                   'Estatus', 'Correo1', 'NivelCorreo1', 'Correo2', 'NivelCorreo2', 
                   'Correo3', 'NivelCorreo3', 'Correo4', 'NivelCorreo4', 
                   'Correo5', 'NivelCorreo5',  
                   'FirmaSolicitante', 'DetallesFirmaSolicitante', 
                   'FirmaDepartamento', 'DetallesFirmaDepartamento', 
                   'FirmaSeguridad', 'DetallesFirmaSeguridad', 
                   'FirmaGerente', 'DetallesFirmaGerente', 'Tipo']
           
        data = []
        for row in results:
            data.append(dict(zip(columns, row)))
        
        return render_template('subordenes2.html', data=data)
    
    except Exception as e:
        flash(f'Error al cargar los datos: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))
    


@app.route('/actualizar_subordenes', methods=['POST'])
@login_required
@nivel_acceso_required
def actualizar_subordenes():
    try:
        # Get the data from the request
        data = request.get_json()
        suborden_id = data.get('id')
        updates = data.get('updates', {})

        # Validate input
        if not suborden_id or not updates:
            return jsonify({'error': 'Datos inválidos'}), 400

        # Prepare the update query dynamically
        update_columns = []
        update_values = []
        for column, value in updates.items():
            # Map the input column names to database column names
            db_column = f'[{column.replace("Correo", "Correo ")}]'
            update_columns.append(f'{db_column} = :val_{column}')
            update_values.append((f'val_{column}', value))

        # Construct the SQL update query
        if update_columns:
            update_query = text(f"""
                UPDATE [DBBI].[dbo].[CierreSucursales4]
                SET {', '.join(update_columns)}
                WHERE [ID] = :id
            """)

            # Add the ID to the update values
            update_values.append(('id', suborden_id))

            # Execute the update
            with db.engine.connect() as conn:
                conn.execute(update_query, dict(update_values))
                conn.commit()

            return jsonify({'message': 'Actualización exitosa'}), 200
        
        return jsonify({'error': 'No hay actualizaciones'}), 400

    except Exception as e:
        # Log the error for debugging
        print(f"Error actualizando subordenes: {str(e)}")
        return jsonify({'error': f'Error al actualizar: {str(e)}'}), 500
    
########################################aplicacion de cierre de farmacia############
@app.route("/aplicacion")
@login_required
def aplicacion():
   # query = text("SELECT distinct Ceco as orden_ceco, FechaIni,  FechaFin, Estatus_General, Tipo_General FROM CierreSucursales4")
    #query = text("SELECT Ceco AS orden_ceco, MAX(FechaIni) AS  FechaIni, CASE WHEN COUNT(*) > COUNT(FechaFin) THEN '-' ELSE CONVERT(VARCHAR, MAX(FechaFin), 23) END AS FechaFin, CASE WHEN COUNT(*) = COUNT(FechaFin) THEN 'Completado' ELSE MAX(Estatus_General) END AS Estatus_General, Tipo_General FROM CierreSucursales4 GROUP BY Ceco, Tipo_General")
    query = text("SELECT Ceco AS orden_ceco, MAX(FechaIni) AS FechaIni, CASE WHEN MAX(FechaFin) IS NOT NULL THEN CONVERT(VARCHAR, MAX(FechaFin), 23) ELSE '-' END AS FechaFin, CASE WHEN MAX(FechaFin) IS NOT NULL THEN 'Completado' ELSE MAX(Estatus_General) END AS Estatus_General, Tipo_General FROM CierreSucursales4 GROUP BY Ceco, Tipo_General")
    ordenes = db.session.execute(query).fetchall()
    return render_template("index_3.html", ordenes=ordenes)
#

# Ruta para mostrar los detalles de una orden
@app.route("/detalles/<detalle_id>", methods=["GET", "POST"])
@login_required
def detalles_view(detalle_id):
    if request.method == "POST":
        ActFijo = request.form["ActFijo"]
        CecoDestino = request.form["CecoDestino"]
        accion = request.form["Accion"]
        query = text("""
            UPDATE CierreSucursales4
            SET [Ceco Destino] = :CecoDestino, Accion = :Accion
            WHERE [Act. Fijo]= :ActFijo
        """)
        db.session.execute(query, {
            "CecoDestino": CecoDestino,
            "Accion": accion,
            "ActFijo": ActFijo
        })
        db.session.commit()
        return redirect(url_for("detalles_view", detalle_id=detalle_id))

    #query = text(" SELECT distinct Departamento as departamento,  FechaIni, FechaFin, estatus, Ceco as ceco FROM CierreSucursales4 WHERE  Departamento<
    #query = text("SELECT DISTINCT Departamento AS departamento, FechaIni,  FechaFin, Ceco AS ceco, CASE WHEN COUNT(CASE WHEN Accion = 'Baja' THEN 1 END) OVER (PARTITION BY Departamento) > 0 AND COUNT(CASE WHEN Accion IS NULL OR Accion = 'Pendiente' THEN 1 END) OVER (PARTITION BY Departamento) > 0 THEN 'Activos Mixto' WHEN COUNT(CASE WHEN Accion = 'Baja' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Baja' WHEN COUNT(CASE WHEN Accion = 'Pendiente' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Pendientes' ELSE 'Otro' END AS Estatus FROM CierreSucursales4 WHERE Departamento<>'BAJA DIRECTA' AND Ceco = :detalle_id")
    query = text("SELECT DISTINCT Departamento AS departamento, FechaIni, FechaFin, Ceco AS ceco, CASE WHEN COUNT(CASE WHEN Accion = 'Baja' THEN 1 END) OVER (PARTITION BY Departamento) > 0 AND COUNT(CASE WHEN Accion IS NULL OR Accion = 'Pendiente' THEN 1 END) OVER (PARTITION BY Departamento) > 0 THEN 'Activos Mixto' WHEN COUNT(CASE WHEN Accion = 'Baja' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Baja' WHEN COUNT(CASE WHEN Accion = 'Pendiente' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Pendientes' WHEN COUNT(CASE WHEN Accion = 'Traspaso' THEN 1 END) OVER (PARTITION BY Departamento) = COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Traspaso' ELSE 'Otro' END AS Estatus FROM CierreSucursales4 WHERE Departamento<>'BAJA DIRECTA' AND Ceco = :detalle_id")



    detalles = db.session.execute(query, {"detalle_id": detalle_id}).fetchall()
    return render_template("detalles_2.html", detalles=detalles)

# Ruta para borrar una orden
@app.route("/borrar/<orden_id>", methods=["POST"])
@login_required
def borrar_orden(orden_id):
    query = text("DELETE FROM CierreSucursales4 WHERE Ceco = :orden_id")
    db.session.execute(query, {"orden_id": orden_id})
    db.session.commit()
    return redirect(url_for("aplicacion"))



@app.route("/subdetalles/<Departamento>/<Ceco>", methods=["GET", "POST"])
@login_required
def subdetalles(Departamento, Ceco):
    
    try:
        # Manejo del POST
        if request.method == "POST":
            try:
                for activo in request.form.getlist("ActFijo"):
                    CecoDestino = request.form.get(f"CecoDestino_{activo}")
                    Accion = request.form.get(f"Accion_{activo}")
                    
                    # Convertir CecoDestino vacío a None
                    CecoDestino = CecoDestino.strip() if CecoDestino else None
                    
                    # Validación solo de Accion
                    if not Accion:
                        raise ValueError("El campo Acción es requerido")
                    
                    # Si es Traspaso, validar CecoDestino
                    if Accion == "Traspaso" and not CecoDestino:
                        raise ValueError(f"El CECO destino es requerido para traspasos en el activo {activo}")
                    
                    # Construir el query y los parámetros
                    params = {
                        "Accion": Accion,
                        "ActFijo": activo,
                        "Departamento": Departamento,
                        "Ceco": Ceco
                    }
                    
                    # Si hay CecoDestino, incluirlo en la actualización
                    if CecoDestino is not None:
                        query = text("""
                            UPDATE CierreSucursales4
                            SET [Ceco Destino] = :CecoDestino, 
                                [Accion] = :Accion
                            WHERE [Act. Fijo] = :ActFijo
                            AND [Departamento] = :Departamento 
                            AND [Ceco] = :Ceco
                        """)
                        params["CecoDestino"] = CecoDestino
                    else:
                        query = text("""
                            UPDATE CierreSucursales4
                            SET [Accion] = :Accion,
                                [Ceco Destino] = NULL
                            WHERE [Act. Fijo] = :ActFijo
                            AND [Departamento] = :Departamento 
                            AND [Ceco] = :Ceco
                        """)
                    
                    db.session.execute(query, params)
                
                db.session.commit()
                return redirect(url_for("subdetalles", Departamento=Departamento, Ceco=Ceco))
            
            except ValueError as ve:
                db.session.rollback()
                return render_template("subdetalles_4.html", 
                                    activos=[], 
                                    mensaje=str(ve), 
                                    Departamento=Departamento, 
                                    Ceco=Ceco)
        
        # Consulta GET optimizada
        query = text("""
            SELECT 
                [ID], [Departamento], [Act. Fijo], [Denominacion del activo fijo],
                [Val. Cont.], [Ceco], [Ceco Destino], [Tipo de Activo],
                [Accion], [Estatus], [Operativo], [Clase], [Fe. Capit.], [Orden],
                [FirmaSolicitante]
            FROM CierreSucursales4 
            WHERE Departamento = :Departamento  and Departamento<>'BAJA DIRECTA'
            AND Ceco = :Ceco
            ORDER BY [ID]
        """)
        
        activos = db.session.execute(query, {
            "Departamento": Departamento, 
            "Ceco": Ceco
        }).fetchall()
        
        if not activos:
            return render_template(
                "subdetalles_5.html", 
                activos=[], 
                mensaje=f"No se encontraron registros para el departamento {Departamento} y CECO {Ceco}.",
                Departamento=Departamento,
                Ceco=Ceco
            )
        
        return render_template(
            "subdetalles_5.html", 
            activos=activos, 
            mensaje="", 
            Departamento=Departamento, 
            Ceco=Ceco
            
        )
        
    except Exception as e:
        db.session.rollback()
        print(f"Error en subdetalles: {str(e)}")  # Log del error
        return render_template(
            "subdetalles_5.html", 
            activos=[], 
            mensaje="Ocurrió un error al procesar su solicitud. Por favor intente más tarde.", 
            Departamento=Departamento, 
            Ceco=Ceco
        )


# Ruta para activos
@app.route("/activos/<activo_id>", methods=["GET", "POST"])
@login_required
def activos_view(activo_id):
    if request.method == "POST":
        Operativo = request.form["Operativo"]
        CecoDestino = request.form["CecoDestino"]
        Accion = request.form["Accion"]
        Observaciones = request.form["Observaciones"]
        
        # Nuevos campos para cuando Acción es "Baja"
        Nombre_del_Proyecto = request.form.get("Nombre_del_Proyecto", "")
        Tipo_de_Proyecto = request.form.get("Tipo_de_Proyecto", "")
        Detalle_relacion_activo_Fijo = request.form.get("Detalle_relacion_activo_Fijo")
        Copia_Factura_compra = request.form.get("Copia_Factura_compra", "")
        Correo_cierre_Sucursal = request.form.get("Correo_cierre_Sucursal", "")
        Informe_Dictamen_tecnico = request.form.get("Informe_Dictamen_tecnico", "")
        Dictamen_Aseguradora = request.form.get("Dictamen_Aseguradora", "")
        Calculo_cobro_para_venta = request.form.get("Calculo_cobro_para_venta", "")
        
        query = text("""
            UPDATE CierreSucursales4
            SET Operativo = :Operativo, 
                [Ceco Destino] = :CecoDestino,
                [Accion] = :Accion,
                [Observaciones] = :Observaciones,
                [Nombre_del_Proyecto] = :Nombre_del_Proyecto,
                [Tipo_de_Proyecto] = :Tipo_de_Proyecto,
                [Detalle o relación del activo Fijo] = :Detalle_relacion_activo_Fijo,
                [Copia Factura de compra] = :Copia_Factura_compra,
                [Correo de cierre de Sucursal] = :Correo_cierre_Sucursal,
                [Informe o Dictamen tecnico] = :Informe_Dictamen_tecnico,
                [Dictamen Aseguradora] = :Dictamen_Aseguradora,
                [Calculo de cobro para venta] = :Calculo_cobro_para_venta
            WHERE [Act. Fijo] = :ActFijo
        """)
        
        db.session.execute(query, {
            "Operativo": Operativo,
            "CecoDestino": CecoDestino,
            "Accion": Accion,
            "Observaciones": Observaciones,
            "Nombre_del_Proyecto": Nombre_del_Proyecto,
            "Tipo_de_Proyecto": Tipo_de_Proyecto,
            "Detalle_relacion_activo_Fijo": Detalle_relacion_activo_Fijo,
            "Copia_Factura_compra": Copia_Factura_compra,
            "Correo_cierre_Sucursal": Correo_cierre_Sucursal,
            "Informe_Dictamen_tecnico": Informe_Dictamen_tecnico,
            "Dictamen_Aseguradora": Dictamen_Aseguradora,
            "Calculo_cobro_para_venta": Calculo_cobro_para_venta,
            "ActFijo": activo_id
        })
        
        db.session.commit()
        
        # Agregando mensaje flash para mostrar confirmación
        flash("Los cambios se han guardado correctamente", "success")
        
        return redirect(url_for("activos_view", activo_id=activo_id))
     
    query = text("SELECT * FROM CierreSucursales4 WHERE [Act. Fijo] = :activo_id")
    activo = db.session.execute(query, {"activo_id": activo_id}).fetchone()
    
    if not activo:
        return f"No se encontró el activo con ID: {activo_id}.", 404
    
    return render_template("activos_5.html", activos=[activo])



####################nuevo adjunto###############

@app.route("/adjuntos/<departamento>/<ceco>")
@login_required
def adjuntos(departamento, ceco):
    try:
        # Get current user information
        current_user_email = session.get('email')  # Asegúrate de que esto obtiene el correo correctamente
        app.logger.info(f"Session email: {current_user_email}")
        
        # Get path information
        query = text("""
            SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path
            FROM [DBBI].[dbo].[CierreSucursales4]
            WHERE [Ceco] = :ceco AND Departamento = :departamento
        """)
        
        # # Get record details to check signature permissions
        # signature_query = text("""
            # SELECT distinct [Correo 1], [Correo 2], [Correo 3], [Correo 4],[Correo 5], [FirmaSolicitante], [FirmaDepartamento],[DetallesFirmaDepartamento],[DetallesFirmaSolicitante]
            # FROM [DBBI].[dbo].[CierreSucursales4]
            # WHERE [Ceco] = :ceco AND Departamento = :departamento
        # """)


        signature_query = text("""
     SELECT distinct c.[Correo 1], c.[Correo 2], c.[Correo 3], c.[Correo 4], c.[Correo 5], g.[Seguridad1], g.[Seguridad2], g.[Seguridad3], g.[Gerente1], g.[Gerente2], g.[Gerente3], 
    c.[FirmaSolicitante],c.[DetallesFirmaSolicitante], c.[FirmaDepartamento], c.[DetallesFirmaDepartamento], 
     c.[FirmaSeguridad],c.[DetallesFirmaSeguridad],c.[FirmaGerente],c.[DetallesFirmaGerente]
    
     FROM [DBBI].[dbo].[CierreSucursales4] c
     CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] g
     WHERE c.[Ceco] = :ceco AND c.[Departamento] = :departamento""")

        
        # Get user details for signature information
        user_query = text("""
            SELECT distinct [Nombre], [Apellido Paterno], [Apellido Materno], [Correo], [Departamento]
            FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
            WHERE [Correo] = :email
        """)
        
        with db.engine.connect() as connection:
            result = connection.execute(query, {"ceco": ceco, "departamento": departamento})
            resultados = result.fetchall()
            
            # Get signature permissions
            sig_result = connection.execute(signature_query, {"ceco": ceco, "departamento": departamento})
            signature_data = sig_result.fetchone()
            
            # Get user details
            user_result = connection.execute(user_query, {"email": current_user_email})
            user_data = user_result.fetchone()

        # Process file list
        archivos = []
        for fila in resultados:
            if fila[0]:
                folder_path = fila[0].strip()
                if os.path.exists(folder_path) and os.path.isdir(folder_path):
                    for file_name in os.listdir(folder_path):
                        if os.path.isfile(os.path.join(folder_path, file_name)):
                            archivos.append(file_name)
        
        # Initializing permissions variables
        can_sign_as_solicitante = False
        can_sign_as_departamento = False
        can_sign_as_seguridad = False
        can_sign_as_gerente = False
        correo1 = ""
        correo2 = ""
        correo3 = ""
        correo4 = ""
        correo5 = ""
        seguridad1 = ""
        seguridad2 = "" 
        seguridad3 = ""
        gerente1 = ""
        gerente2 = "" 
        gerente3 = ""
        firma_solicitante = None
        firma_departamento = None
        firma_seguridad = None
        firma_gerente = None
        DetallesFirmaDepartamento = ""
        DetallesFirmaSolicitante = ""
        DetallesfirmaSeguridad = ""
        DetallesfirmaGerente = ""
        
        if signature_data and current_user_email:
            correo1 = signature_data[0] if signature_data[0] else ""
            correo2 = signature_data[1] if signature_data[1] else ""
            correo3 = signature_data[2] if signature_data[2] else ""
            correo4 = signature_data[3] if signature_data[3] else ""
            correo5 = signature_data[4] if signature_data[4] else ""
            seguridad1 = signature_data[5] if signature_data[5] else ""
            seguridad2 = signature_data[6] if signature_data[6] else ""
            seguridad3 = signature_data[7] if signature_data[7] else ""
            gerente1 = signature_data[8] if signature_data[8] else ""
            gerente2 = signature_data[9] if signature_data[9] else ""
            gerente3 = signature_data[10] if signature_data[10] else ""
            firma_solicitante = signature_data[11] if len(signature_data) > 11 else None
            DetallesFirmaSolicitante = signature_data[12] if len(signature_data) > 12 and signature_data[12] else ""
            firma_departamento = signature_data[13] if len(signature_data) > 13 else None
            DetallesFirmaDepartamento = signature_data[14] if len(signature_data) > 14 else None
            firma_seguridad = signature_data[15] if len(signature_data) > 15 else None
            DetallesfirmaSeguridad = signature_data[16] if len(signature_data) > 16 else None
            firma_gerente = signature_data[17] if len(signature_data) > 17 else None
            DetallesfirmaGerente = signature_data[18] if len(signature_data) > 18 and signature_data[18] else ""
            

            
            # Normalizar correos para comparación (convertir a minúsculas y quitar espacios)
            current_user_email = current_user_email.lower().strip()
            correo1 = correo1.lower().strip() if correo1 else ""
            correo2 = correo2.lower().strip() if correo2 else ""
            correo3 = correo3.lower().strip() if correo3 else ""
            correo4 = correo4.lower().strip() if correo4 else ""
            correo5 = correo5.lower().strip() if correo5 else ""
            seguridad1 = seguridad1.lower().strip() if seguridad1 else ""
            seguridad2 = seguridad2.lower().strip() if seguridad2 else ""
            seguridad3 = seguridad3.lower().strip() if seguridad3 else ""
            gerente1 = gerente1.lower().strip() if gerente1 else ""
            gerente2 = gerente2.lower().strip() if gerente2 else ""
            gerente3 = gerente3.lower().strip() if gerente3 else ""          
            
            
           
            # app.logger.info(f"Current email: {current_user_email}")
            # app.logger.info(f"Correo1: {correo1}, Correo2: {correo2}, Correo3: {correo3}, Correo4: {correo4}, Correo5: {correo5}")
            # app.logger.info(f"FirmaSolicitante: {firma_solicitante}, FirmaDepartamento: {firma_departamento}")
            app.logger.info(f"Current email: {current_user_email}")
            app.logger.info(f"Correo1: {correo1}, Correo2: {correo2}, Correo3: {correo3}, Correo4: {correo4}, Correo5: {correo5}, Correo5: {correo5}, Seguridad1: {seguridad1}, Seguridad2: {seguridad2}, Seguridad3: {seguridad3}, Gerente1: {gerente1}, Gerente2: {gerente2}, Gerente3: {gerente3}")
            app.logger.info(f"FirmaSolicitante: {firma_solicitante}, FirmaDepartamento: {firma_departamento}, FirmaSeguridad: {firma_seguridad}, FirmaGerente: {firma_gerente}")
            
            # Verificar si el usuario puede firmar como solicitante
            if (current_user_email == correo1 or current_user_email == correo2 or current_user_email == correo3) and firma_solicitante != "Verdadero":
                can_sign_as_solicitante = True
            
            # Verificar si el usuario puede firmar como departamento
            # Sólo habilitar si firma solicitante ya está firmada
            #if current_user_email == correo4 and firma_departamento != "Verdadero":
            if current_user_email == correo4 or current_user_email == correo5 and firma_departamento != "Verdadero":
                if firma_solicitante == "Verdadero":
                    can_sign_as_departamento = True
             # Sólo habilitar si firma seguridad ya está firmada       
            if current_user_email == seguridad1 or current_user_email == seguridad2 or current_user_email == seguridad3  and firma_seguridad != "Verdadero":
                if firma_solicitante == "Verdadero" and firma_departamento == "Verdadero":
                    can_sign_as_seguridad = True
            # Sólo habilitar si firma seguridad ya está firmada       
            if current_user_email == gerente1 or current_user_email == gerente2 or current_user_email == gerente3  and firma_gerente != "Verdadero":
                if firma_solicitante == "Verdadero" and firma_departamento == "Verdadero" and firma_seguridad == "Verdadero":
                    can_sign_as_gerente = True
        
        # User full name for signature details
        user_full_name = ""
        if user_data:
            nombre = user_data[0] if user_data[0] else ""
            apellido_paterno = user_data[1] if user_data[1] else ""
            apellido_materno = user_data[2] if user_data[2] else ""
            user_full_name = f"{nombre} {apellido_paterno} {apellido_materno}"  # Cambié las comas por espacios

        app.logger.info(f"Usuario: {current_user_email}, Puede firmar como solicitante: {can_sign_as_solicitante}, Puede firmar como departamento: {can_sign_as_departamento}, Puede firmar como seguridad: {can_sign_as_seguridad}, Puede firmar como gerente: {can_sign_as_gerente}")

        return render_template(
            'Adjuntos_4.html', 
            archivos=archivos, 
            departamento=departamento, 
            ceco=ceco,
            can_sign_as_solicitante=can_sign_as_solicitante,
            can_sign_as_departamento=can_sign_as_departamento,
            can_sign_as_seguridad=can_sign_as_seguridad,
            can_sign_as_gerente=can_sign_as_gerente,
            user_full_name=user_full_name,
            # Nuevas variables para debugging
            correo1=correo1,
            correo2=correo2,
            correo3=correo3,
            correo4=correo4,
            correo5=correo5,
            seguridad1=seguridad1,
            seguridad2=seguridad2,
            seguridad3=seguridad3,
            gerente1=gerente1,
            gerente2=gerente2,
            gerente3=gerente3,
            firma_solicitante=firma_solicitante,
            firma_departamento=firma_departamento,
            firma_seguridad=firma_seguridad,
            firma_gerente=firma_gerente,
            DetallesFirmaDepartamento=DetallesFirmaDepartamento,
            DetallesFirmaSolicitante=DetallesFirmaSolicitante,
            DetallesfirmaSeguridad=DetallesfirmaSeguridad,
            DetallesfirmaGerente = DetallesfirmaGerente
            

        )

    except Exception as e:
        app.logger.error(f"Error en adjuntos: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to save signatures
# Modificación de la función guardar_firmas
@app.route("/guardar_firmas/<departamento>/<ceco>", methods=["POST"])
@login_required
def guardar_firmas(departamento, ceco):
    try:
        current_user_email = session.get('email')
        if not current_user_email:
            return jsonify({'error': 'Usuario no autenticado'}), 401

        # Obtener datos del formulario
        solicitante_firma = request.form.get('solicitante')
        departamento_firma = request.form.get('departamento')
        seguridad_firma = request.form.get('seguridad')
        gerente_firma = request.form.get('gerente')

        app.logger.info(f"Guardando firmas: solicitante={solicitante_firma}, departamento={departamento_firma}, seguridad={seguridad_firma}, gerente={gerente_firma}")

        # Obtener los detalles del usuario actual
        user_query = text("""
            SELECT [Nombre], [Apellido Paterno], [Apellido Materno]
            FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
            WHERE [Correo] = :email
        """)

        check_query = text("""
           SELECT distinct c.[Correo 1], c.[Correo 2], c.[Correo 3], c.[Correo 4], c.[Correo 5], g.[Seguridad1], g.[Seguridad2], g.[Seguridad3], g.[Gerente1], g.[Gerente2], g.[Gerente3], 
          c.[FirmaSolicitante], c.[DetallesFirmaSolicitante], c.[FirmaDepartamento], c.[DetallesFirmaDepartamento], 
          c.[FirmaSeguridad], c.[DetallesFirmaSeguridad], c.[FirmaGerente], c.[DetallesFirmaGerente]
          FROM [DBBI].[dbo].[CierreSucursales4] c
           CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] g
           WHERE c.[Ceco] = :ceco AND c.[Departamento] = :departamento""")

        with db.engine.connect() as connection:
            user_result = connection.execute(user_query, {"email": current_user_email}).fetchone()
            if not user_result:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            nombre, apellido_paterno, apellido_materno = user_result

            check_result = connection.execute(check_query, {"ceco": ceco, "departamento": departamento}).fetchone()
            if not check_result:
                return jsonify({'error': 'Registro de firma no encontrado'}), 404

            # Desempaquetar todos los valores
            correo1, correo2, correo3, correo4, correo5, seguridad1, seguridad2, seguridad3, gerente1, gerente2, gerente3, firma_solicitante_actual, detalles_firma_solicitante, firma_departamento_actual, detalles_firma_departamento, firma_seguridad_actual, detalles_firma_seguridad, firma_gerente_actual, detalles_firma_gerente = check_result

        # Normalizar correos para comparación
        user_email = current_user_email.lower().strip()
        correo1 = correo1.lower().strip() if correo1 else ""
        correo2 = correo2.lower().strip() if correo2 else ""
        correo3 = correo3.lower().strip() if correo3 else ""
        correo4 = correo4.lower().strip() if correo4 else ""
        correo5 = correo5.lower().strip() if correo5 else ""
        seguridad1 = seguridad1.lower().strip() if seguridad1 else ""
        seguridad2 = seguridad2.lower().strip() if seguridad2 else ""
        seguridad3 = seguridad3.lower().strip() if seguridad3 else ""
        gerente1 = gerente1.lower().strip() if gerente1 else ""
        gerente2 = gerente2.lower().strip() if gerente2 else ""
        gerente3 = gerente3.lower().strip() if gerente3 else ""           

        # Construir los valores a actualizar
        update_parts = []
        update_params = {"ceco": ceco, "departamento": departamento}

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_name = f"{nombre} {apellido_paterno} {apellido_materno} - {timestamp}"
        fecha_actual = date.today().strftime("%Y-%m-%d")

        # Variable para rastrear si se debe enviar un correo y a quién
        notification_type = None

        # Verificar y actualizar firma del solicitante
        can_sign_as_solicitante = (user_email == correo1 or user_email == correo2 or user_email == correo3) and firma_solicitante_actual != "Verdadero"
        solicitante_firma_valor = request.form.get('solicitante', '')

        if solicitante_firma and can_sign_as_solicitante:
            # Establecer el valor de FirmaSolicitante según la selección del radio button
            update_parts.append("[FirmaSolicitante] = :solicitante_firma_valor")
            update_params["solicitante_firma_valor"] = 'Verdadero' if solicitante_firma_valor == 'si' else 'Falso'
            
            update_parts.append("[DetallesFirmaSolicitante] = :solicitante_details")
            update_params["solicitante_details"] = full_name
            app.logger.info(f"Firmando como solicitante: {full_name}, Valor: {update_params['solicitante_firma_valor']}")
            
            # Si el valor es "si" (Verdadero), programar notificación para departamento
            if solicitante_firma_valor == 'si':
                notification_type = 'solicitante_to_departamento'

        # Verificar y actualizar firma del departamento
        can_sign_as_departamento = (user_email == correo4 or user_email == correo5) and firma_departamento_actual != "Verdadero" and firma_solicitante_actual == "Verdadero"
        departamento_firma_valor = request.form.get('departamento', '')
        if departamento_firma and can_sign_as_departamento:
            # Establecer el valor de FirmaDepartamento según la selección del radio button
            update_parts.append("[FirmaDepartamento] = :departamento_firma_valor")
            update_params["departamento_firma_valor"] = 'Verdadero' if departamento_firma_valor == 'si' else 'Falso'

            update_parts.append("[DetallesFirmaDepartamento] = :departamento_details")
            update_params["departamento_details"] = full_name
            app.logger.info(f"Firmando como departamento: {full_name}, Valor: {update_params['departamento_firma_valor']}")
            
            # Si el valor es "si" (Verdadero), programar notificación para seguridad
            if departamento_firma_valor == 'si':
                notification_type = 'departamento_to_seguridad'

        # Verificar y actualizar firma de seguridad
        can_sign_as_seguridad = (user_email == seguridad1 or user_email == seguridad2 or user_email == seguridad3) and firma_departamento_actual == "Verdadero" and firma_solicitante_actual == "Verdadero" and firma_seguridad_actual != "Verdadero"
        seguridad_firma_valor = request.form.get('seguridad', '')
        if seguridad_firma and can_sign_as_seguridad: 
            # Establecer el valor de FirmaSeguridad según la selección del radio button
            update_parts.append("[FirmaSeguridad] = :seguridad_firma_valor")
            update_params["seguridad_firma_valor"] = 'Verdadero' if seguridad_firma_valor == 'si' else 'Falso'  
            
            update_parts.append("[DetallesFirmaSeguridad] = :seguridad_details")
            update_params["seguridad_details"] = full_name
            app.logger.info(f"Firmando como seguridad: {full_name}, Valor: {update_params['seguridad_firma_valor']}")
            
            # Si el valor es "si" (Verdadero), programar notificación para gerencia
            if seguridad_firma_valor == 'si':
                notification_type = 'seguridad_to_gerencia'

        # Verificar y actualizar firma de gerente
        can_sign_as_gerente = (user_email == gerente1 or user_email == gerente2 or user_email == gerente3) and firma_departamento_actual == "Verdadero" and firma_solicitante_actual == "Verdadero" and firma_seguridad_actual == "Verdadero" and firma_gerente_actual != "Verdadero"
        gerente_firma_valor = request.form.get('gerente', '')
        
        if gerente_firma and can_sign_as_gerente:
           # Establecer el valor de FirmaGerente según la selección del radio button
           update_parts.append("[FirmaGerente] = :gerente_firma_valor")
           update_params["gerente_firma_valor"] = 'Verdadero' if gerente_firma_valor == 'si' else 'Falso'
           # Agregar detalles de la firma
           update_parts.append("[DetallesFirmaGerente] = :gerente_details")
           update_params["gerente_details"] = full_name
           # Agregar la fecha actual
           update_parts.append("[FechaFin] = :fecha_fin")
           update_params["fecha_fin"] = fecha_actual
           app.logger.info(f"Firmando como Gerente: {full_name}, Valor: {update_params['gerente_firma_valor']}, Fecha: {fecha_actual}")

        # Ejecutar la actualización si hay cambios
        if update_parts:
            update_query = text(f"""
                UPDATE [DBBI].[dbo].[CierreSucursales4]
                SET {', '.join(update_parts)}
                WHERE [Ceco] = :ceco AND Departamento = :departamento
            """)

            with db.engine.begin() as connection:  # Asegura una transacción y libera recursos
                connection.execute(update_query, update_params)

            flash("Firmas guardadas correctamente", "success")
            app.logger.info("Firmas actualizadas correctamente")
            
            # Enviar notificación por correo según la etapa del flujo
            if notification_type:
                notification_result = send_signature_notification2(ceco, departamento, notification_type)
                if 'error' in notification_result:
                    app.logger.warning(f"Error al enviar notificación: {notification_result['error']}")
                    flash(f"La firma se guardó pero ocurrió un error al enviar la notificación: {notification_result['error']}", "warning")
                else:
                    app.logger.info(f"Notificación enviada: {notification_result}")
                    flash("Notificación enviada correctamente", "success")

        else:
            flash("No se realizaron cambios en las firmas", "warning")
            app.logger.warning("No se realizaron cambios en las firmas")

        return redirect(url_for('adjuntos', departamento=departamento, ceco=ceco))

    except Exception as e:
        app.logger.error(f"Error en guardar_firmas: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

def send_signature_notification2(ceco, departamento, notification_type):
    try:
        # Conexión a la base de datos usando el engine existente
        conn = db.engine.connect()
        
        # Consultar los contactos según el CECO y departamento
        query_contacts = text("""
            SELECT distinct
                cs4.[Correo 1] as correo1, 
                cs4.[Correo 2] as correo2, 
                cs4.[Correo 3] as correo3, 
                cs4.[Correo 4] as correo4, 
                cs4.[Correo 5] as correo5,
                csg.[Seguridad1] as seguridad1, 
                csg.[Seguridad2] as seguridad2, 
                csg.[Seguridad3] as seguridad3,
                csg.[Gerente1] as gerente1, 
                csg.[Gerente2] as gerente2, 
                csg.[Gerente3] as gerente3
            FROM [DBBI].[dbo].[CierreSucursales4] cs4
            CROSS JOIN [DBBI].[dbo].[CierreSucursales_Gerentes] csg
            WHERE cs4.[Ceco] = :ceco AND cs4.[Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
        """)
        
        result = conn.execute(query_contacts, {"ceco": ceco, "departamento": departamento})
        result_contacts = result.fetchone()
        
        if not result_contacts:
            app.logger.error(f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}")
            return {"error": f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}"}
        
        # Convertir Row a diccionario si es necesario
        if not isinstance(result_contacts, dict):
            result_contacts = dict(result_contacts._mapping)
        
        # Consultar los datos de los activos para incluir en el correo
        query_assets = text("""
            SELECT distinct
                [Departamento],
                [Act. Fijo],
                [Clase],
                [Denominacion del activo fijo],
                [Orden],
                [Ceco],
                [Farmacia],
                [FechaIni]
            FROM [DBBI].[dbo].[CierreSucursales4]
            WHERE [Ceco] = :ceco AND [Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
        """)
        
        result_assets = conn.execute(query_assets, {"ceco": ceco, "departamento": departamento}).fetchall()
        
        if not result_assets:
            app.logger.error(f"No se encontraron activos para CECO: {ceco}, Departamento: {departamento}")
            return {"error": f"No se encontraron activos para CECO: {ceco}, Departamento: {departamento}"}
        
        # Configurar destinatarios según el tipo de notificación
        to_emails = []
        cc_emails = []
        subject_prefix = ""
        
        # Determinar destinatarios basados en el tipo de notificación
        if notification_type == 'solicitante_to_departamento':
            # Cuando Solicitante firma, notificar a Departamento (correo4, correo5)
            subject_prefix = "Se requiere de su Firma electrónica Departamento"
            
            # Destinatarios principales: Departamento
            dept_keys = ["correo4", "correo5"]
            for key in dept_keys:
                if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                    to_emails.append(result_contacts[key])
            
            # Copia: Solicitantes, Seguridad, Gerencia
            cc_keys = ["correo1", "correo2", "correo3", "seguridad1", "seguridad2", "seguridad3", "gerente1", "gerente2", "gerente3"]
            for key in cc_keys:
                if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                    cc_emails.append(result_contacts[key])
                    
        elif notification_type == 'departamento_to_seguridad':
            # Cuando Departamento firma, notificar a Seguridad
            subject_prefix = "Se requiere de su Firma electrónica Seguridad"
            
            # Destinatarios principales: Seguridad
            security_keys = ["seguridad1", "seguridad2", "seguridad3"]
            for key in security_keys:
                if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                    to_emails.append(result_contacts[key])
            
            # Copia: Solicitantes, Departamento, Gerencia
            cc_keys = ["correo1", "correo2", "correo3", "correo4", "correo5", "gerente1", "gerente2", "gerente3"]
            for key in cc_keys:
                if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                    cc_emails.append(result_contacts[key])
                    
        elif notification_type == 'seguridad_to_gerencia':
            # Cuando Seguridad firma, notificar a Gerencia
            subject_prefix = "Se requiere de su Firma electrónica Gerencia"
            
            # Destinatarios principales: Gerencia
            manager_keys = ["gerente1", "gerente2", "gerente3"]
            for key in manager_keys:
                if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                    to_emails.append(result_contacts[key])
            
            # Copia: Solicitantes, Departamento, Seguridad
            cc_keys = ["correo1", "correo2", "correo3", "correo4", "correo5", "seguridad1", "seguridad2", "seguridad3"]
            for key in cc_keys:
                if key in result_contacts and result_contacts[key] and result_contacts[key] != "None" and result_contacts[key] is not None:
                    cc_emails.append(result_contacts[key])
        
        # Si no hay destinatarios principales, reportar error
        if not to_emails:
            app.logger.error(f"No se encontraron destinatarios para notificación tipo: {notification_type}")
            return {"error": f"No se encontraron destinatarios para notificación tipo: {notification_type}"}
        
        # Crear tabla HTML con los datos de los activos
        html_table = """
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Departamento</th>
                <th>Act. Fijo</th>
                <th>Clase</th>
                <th>Denominacion</th>
                <th>Orden</th>
                <th>CECO</th>
                <th>Farmacia</th>
                <th>Fecha</th>
            </tr>
        """
        
        # Llenar la tabla con los datos
        for row in result_assets:
            # Convertir Row a diccionario si es necesario
            if hasattr(row, '_mapping'):
                row_dict = dict(row._mapping)
            else:
                row_dict = row
                
            html_table += f"""
            <tr>
                <td>{row_dict.get('Departamento', '')}</td>
                <td>{row_dict.get('Act. Fijo', '')}</td>
                <td>{row_dict.get('Clase', '')}</td>
                <td>{row_dict.get('Denominacion del activo fijo', '')}</td>
                <td>{row_dict.get('Orden', '')}</td>
                <td>{row_dict.get('Ceco', '')}</td>
                <td>{row_dict.get('Farmacia', '')}</td>
                <td>{row_dict.get('FechaIni', '')}</td>
            </tr>
            """
        
        html_table += "</table>"
        
        # Configurar el mensaje
        msg = MIMEMultipart()
        msg['From'] = 'CierreFarmacias@benavides.com.mx'
        msg['To'] = ", ".join(to_emails)
        if cc_emails:
            msg['Cc'] = ", ".join(cc_emails)
        
        # Asunto del correo según el tipo de notificación
        msg['Subject'] = f"{subject_prefix} - CECO: {ceco}, Departamento: {departamento}"
        
        # Cuerpo del correo
        body = f"""
        <html>
        <body>
            <p>Buen día. Se requiere su firma electrónica en el sistema.</p>
            {html_table}
            <p>Favor de proceder con su firma electrónica en esta liga http://10.30.43.103:5020/.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Configuración del servidor SMTP
        smtp_server = 'casarray.benavides.com.mx'
        smtp_port = 25
        smtp_user = 'CierreFarmacias@benavides.com.mx'
        
        # Enviar el correo
        try:
            all_recipients = to_emails + cc_emails
            app.logger.info(f"Intentando enviar correo a: {', '.join(all_recipients)}")
            app.logger.info(f"SMTP Server: {smtp_server}:{smtp_port}")
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            app.logger.info("Conexión al servidor SMTP establecida")
            
            server.sendmail(msg['From'], all_recipients, msg.as_string())
            app.logger.info(f"Correo enviado exitosamente a: {', '.join(all_recipients)}")
            app.logger.info(f"Asunto: {msg['Subject']}")
            server.quit()
            app.logger.info("Conexión al servidor SMTP cerrada")
            
            return {
                "success": True,
                "notification_type": notification_type,
                "to": to_emails,
                "cc": cc_emails,
                "subject": msg['Subject']
            }
        except Exception as email_error:
            app.logger.error(f"Error al enviar el correo: {str(email_error)}")
            return {"error": f"Error al enviar el correo: {str(email_error)}"}
        
    except Exception as e:
        app.logger.error(f"Error general en send_signature_notification: {str(e)}")
        return {"error": str(e)}





@app.route("/eliminar_archivos/<departamento>/<ceco>", methods=["POST"])
@login_required
def eliminar_archivos(departamento, ceco):
    try:
        # Get files to delete from JSON payload
        files_to_delete = request.json.get('files', [])
        
        # Get path information (similar to your existing query)
        query = text("""
            SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path
            FROM [DBBI].[dbo].[CierreSucursales4]
            WHERE [Ceco] = :ceco AND Departamento = :departamento
        """)
        
        with db.engine.connect() as connection:
            result = connection.execute(query, {"ceco": ceco, "departamento": departamento})
            resultados = result.fetchall()
        
        # Process file list
        if resultados and resultados[0][0]:
            folder_path = resultados[0][0].strip()
            deleted_files = []
            
            for filename in files_to_delete:
                full_file_path = os.path.join(folder_path, filename)
                
                # Security check: Ensure the file is in the correct directory
                if os.path.commonpath([folder_path, full_file_path]) == folder_path:
                    if os.path.exists(full_file_path):
                        os.remove(full_file_path)
                        deleted_files.append(filename)
        
        return jsonify({
            "success": True, 
            "deleted_files": deleted_files
        })
    
    except Exception as e:
        app.logger.error(f"Error en eliminar_archivos: {str(e)}")
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500




# Ruta para descargar archivos
@app.route('/descargar/<departamento>/<ceco>/<filename>')
@login_required
def descargar(departamento, ceco, filename):
    try:
        query = text("""
            SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path
            FROM [DBBI].[dbo].[CierreSucursales4]
            WHERE [Ceco] = :ceco AND Departamento = :departamento
        """)
        with db.engine.connect() as connection:
            result = connection.execute(query, {"ceco": ceco, "departamento": departamento})
            resultados = result.fetchall()

        if not resultados:
            return jsonify({'error': 'No se encontró la ruta en la base de datos'}), 404

        folder_path = resultados[0][0].strip()
        folder_path = os.path.normpath(folder_path)

        if not os.path.exists(folder_path):
            return jsonify({'error': f'La ruta no existe: {folder_path}'}), 404

        return send_from_directory(folder_path, filename, as_attachment=True)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para subir archivos
@app.route('/subir/<departamento>/<ceco>', methods=['POST'])
@login_required
def subir(departamento, ceco):
    if 'archivo' not in request.files:
        return 'No file part', 400
    archivo = request.files['archivo']
    if archivo.filename == '':
        return 'No selected file', 400

    try:
        query = text("""
            SELECT DISTINCT 'P:\\UPLOAD\\' + [Departamento] + '\\' + [Ceco] AS Path
            FROM [DBBI].[dbo].[CierreSucursales4]
            WHERE [Ceco] = :ceco AND Departamento = :departamento
        """)
        with db.engine.connect() as connection:
            result = connection.execute(query, {"ceco": ceco, "departamento": departamento})
            resultados = result.fetchall()

        if not resultados:
            return 'No se encontró una ruta válida en la base de datos', 400

        folder_path = resultados[0][0].strip()
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        archivo.save(os.path.join(folder_path, archivo.filename))
        return redirect(url_for('adjuntos', departamento=departamento, ceco=ceco))

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para generar PDF
@app.route('/PDF/<departamento>/<ceco>', methods=['POST'])
@login_required
def generar_pdf(departamento, ceco):
    try:
        scripts = [
            ("P:/CierreFarmacias/Scripts/python.exe", "P:/CierreFarmacias/PDF7_Traspaso.py", departamento, ceco),
            ("P:/CierreFarmacias/Scripts/python.exe", "P:/CierreFarmacias/PDF_BAJA.py", departamento, ceco),
            ("P:/CierreFarmacias/Scripts/python.exe", "P:/CierreFarmacias/PDF_Tecnico.py", departamento, ceco),
            ("P:/CierreFarmacias/Scripts/python.exe", "P:/CierreFarmacias/pdf_Recoleccion.py", departamento, ceco)
        ]
        for script in scripts:
            result = subprocess.run(script, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(result.stderr)

        return jsonify({'success': True, 'message': 'PDFs generados correctamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    

###############################Portal de accesos#############################


# Modelo de datos adaptado a la tabla SQL Server existente
class Usuario(db.Model):
    __tablename__ = 'CierreSucursales_Control_Accesos_Web'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Apellido_Paterno = db.Column(db.String(100), nullable=False, name='Apellido Paterno')
    Apellido_Materno = db.Column(db.String(100), nullable=False, name='Apellido Materno')
    Usuario = db.Column(db.String(100), nullable=False, unique=True)
    Password = db.Column(db.String(100), nullable=False)
    Departamento = db.Column(db.String(100), nullable=False)
    Nivel_Acceso = db.Column(db.Integer, nullable=False, name='Nivel Acceso')
    Correo = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f'<Usuario {self.Nombre} {self.Apellido_Paterno}>'

# # Rutas
# @app.route('/')
# def index():
    # return redirect(url_for('accesos'))

@app.route('/accesos', methods=['GET', 'POST'])
@login_required
def accesos():
    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        apellido_paterno = request.form.get('apellido_paterno')
        apellido_materno = request.form.get('apellido_materno')
        password = request.form.get('password')
        departamento = request.form.get('departamento')
        nivel_acceso = request.form.get('nivel_acceso')
        correo = request.form.get('correo')
        
        # Generar usuario a partir del correo
        usuario = correo.split('@')[0]
        
        # Validar que todos los campos estén llenos
        if not all([nombre, apellido_paterno, apellido_materno, password, departamento, nivel_acceso, correo]):
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('accesos'))
        
        # Verificar si el correo ya existe usando SQL directo
        try:
            conn = db.engine.connect()
            result = conn.execute(text(f"SELECT Correo FROM CierreSucursales_Control_Accesos_Web WHERE Correo = '{correo}'"))
            usuario_existente = result.fetchone()
            conn.close()
            
            if usuario_existente:
                flash('El correo ya está registrado', 'danger')
                return redirect(url_for('accesos'))
        except Exception as e:
            flash(f'Error al verificar correo: {str(e)}', 'danger')
            return redirect(url_for('accesos'))
        
        # Usar SQL directo para insertar
        try:
            sql = text("""
                INSERT INTO CierreSucursales_Control_Accesos_Web 
                ([Nombre], [Apellido Paterno], [Apellido Materno], [Usuario], [Password], [Departamento], [Nivel Acceso], [Correo])
                VALUES (:nombre, :apellido_paterno, :apellido_materno, :usuario, :password, :departamento, :nivel_acceso, :correo)
            """)
            
            conn = db.engine.connect()
            conn.execute(sql, {
                'nombre': nombre,
                'apellido_paterno': apellido_paterno,
                'apellido_materno': apellido_materno,
                'usuario': usuario,
                'password': password,
                'departamento': departamento,
                'nivel_acceso': int(nivel_acceso),
                'correo': correo
            })
            conn.commit()
            conn.close()
            
            flash('Usuario guardado correctamente', 'success')
            return redirect(url_for('lista_usuarios'))
        except Exception as e:
            flash(f'Error al guardar: {str(e)}', 'danger')
            return redirect(url_for('accesos'))
    
    return render_template('accesos.html')

@app.route('/usuarios')
@login_required
def lista_usuarios():
    try:
        # Usar SQL directo para obtener todos los usuarios
        conn = db.engine.connect()
        result = conn.execute(text("""
            SELECT [id], [Nombre], [Apellido Paterno], [Apellido Materno], [Usuario], 
                   [Password], [Departamento], [Nivel Acceso], [Correo]
            FROM [DBBI].[dbo].[CierreSucursales_Control_Accesos_Web]
        """))
        
        # Convertir result en lista de diccionarios
        usuarios = []
        for row in result:
            usuario = {
                'id': row[0],
                'Nombre': row[1],
                'Apellido_Paterno': row[2],
                'Apellido_Materno': row[3],
                'Usuario': row[4],
                'Password': row[5],
                'Departamento': row[6],
                'Nivel_Acceso': row[7],
                'Correo': row[8]
            }
            usuarios.append(usuario)
        
        conn.close()
        return render_template('usuarios.html', usuarios=usuarios)
    except Exception as e:
        flash(f'Error al cargar usuarios: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/actualizar_usuario', methods=['POST'])
@login_required
def actualizar_usuario():
    try:
        id = request.form.get('id')
        nombre = request.form.get('nombre')
        apellido_paterno = request.form.get('apellido_paterno')
        apellido_materno = request.form.get('apellido_materno')
        password = request.form.get('password')
        departamento = request.form.get('departamento')
        nivel_acceso = request.form.get('nivel_acceso')
        
        # Usar SQL directo para actualizar
        sql = text("""
            UPDATE CierreSucursales_Control_Accesos_Web
            SET [Nombre] = :nombre,
                [Apellido Paterno] = :apellido_paterno,
                [Apellido Materno] = :apellido_materno,
                [Password] = :password,
                [Departamento] = :departamento,
                [Nivel Acceso] = :nivel_acceso
            WHERE id = :id
        """)
        
        conn = db.engine.connect()
        conn.execute(sql, {
            'nombre': nombre,
            'apellido_paterno': apellido_paterno,
            'apellido_materno': apellido_materno,
            'password': password,
            'departamento': departamento,
            'nivel_acceso': int(nivel_acceso),
            'id': int(id)
        })
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Usuario actualizado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    

@app.route('/eliminar_usuario', methods=['POST'])
@login_required
def eliminar_usuario():
    try:
        id = request.form.get('id')
        
        # Usar SQL directo para eliminar
        sql = text("""
            DELETE FROM CierreSucursales_Control_Accesos_Web
            WHERE id = :id
        """)
        
        conn = db.engine.connect()
        conn.execute(sql, {'id': int(id)})
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Usuario eliminado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500




#######################Grafico#####################

# @app.route('/grafico')
# def index():
#    # return render_template('grafico.html')

@app.route('/data')
def get_data():
    query = text("""
        SELECT Departamento, SUM(cont) AS cont, Accion
        FROM (
            SELECT Departamento, Accion, COUNT(*) AS cont
            FROM DBBI.dbo.CierreSucursales4
            WHERE Departamento <> 'BAJA DIRECTA'
            GROUP BY Departamento, Accion
        ) AS subquery
        GROUP BY Departamento, Accion
    """)
    result = db.session.execute(query)
    data = [["Departamento", "Cantidad", "Accion"]] + [list(row) for row in result]
    return jsonify(data)



@app.route('/summary')
def get_summary():
    query = text("""
        SELECT Departamento, SUM(cont) AS total
        FROM (
            SELECT Departamento, Accion, COUNT(*) AS cont
            FROM DBBI.dbo.CierreSucursales4
            WHERE Departamento <> 'BAJA DIRECTA'
            GROUP BY Departamento, Accion
        ) AS subquery
        GROUP BY Departamento
    """)
    result = db.session.execute(query)
    data = [["Departamento", "Total"]] + [list(row) for row in result]
    return jsonify(data)


from sqlalchemy import text

# Ruta para listar los usuarios de seguridad y gerencia
@app.route('/lista_Seguridad_Gerencias')
@login_required
def lista_Seguridad_Gerencias():
    try:
        # Obteniendo una conexión usando SQLAlchemy correctamente
        conn = db.engine.connect()
        
        # Usar text() para convertir la cadena SQL en un objeto ejecutable
        query = text("""
            SELECT [ID], [Seguridad1], [Seguridad2], [Seguridad3], 
                   [Gerente1], [Gerente2], [Gerente3]  
            FROM [DBBI].[dbo].[CierreSucursales_Gerentes]
            ORDER BY [ID] DESC
        """)
        
        # Ejecutar consulta con el objeto text
        result = conn.execute(query)
        
        # Convertir los resultados a una lista de diccionarios
        Seguridad_Gerencias = []
        for row in result:
            Seguridad_Gerencias.append({
                'id': row[0],
                'Seguridad1': row[1],
                'Seguridad2': row[2],
                'Seguridad3': row[3],
                'Gerente1': row[4],
                'Gerente2': row[5],
                'Gerente3': row[6]
            })
        
        # Cerrar la conexión
        conn.close()
        
        return render_template('lista_Seguridad_Gerencias.html', Seguridad_Gerencias=Seguridad_Gerencias)
    
    except Exception as e:
        return f"Error en la consulta: {str(e)}", 500

# Ruta para actualizar un usuario de seguridad y gerencia
@app.route('/actualizar_Seguridad_Gerencia', methods=['POST'])
@login_required
def actualizar_Seguridad_Gerencia():
    if request.method == 'POST':
        try:
            id = request.form['id']
            seguridad1 = request.form['Seguridad1']
            seguridad2 = request.form['Seguridad2']
            seguridad3 = request.form['Seguridad3']
            gerente1 = request.form['Gerente1']
            gerente2 = request.form['Gerente2']
            gerente3 = request.form['Gerente3']
            
            # Obteniendo una conexión
            conn = db.engine.connect()
            
            # Crear un objeto text() para la consulta de actualización
            query = text("""
                UPDATE [DBBI].[dbo].[CierreSucursales_Gerentes]
                SET [Seguridad1] = :seg1, [Seguridad2] = :seg2, [Seguridad3] = :seg3,
                    [Gerente1] = :ger1, [Gerente2] = :ger2, [Gerente3] = :ger3
                    
                WHERE [ID] = :id
            """)
            
            # Ejecutar la consulta con los parámetros
            conn.execute(query, {
                'seg1': seguridad1, 
                'seg2': seguridad2, 
                'seg3': seguridad3, 
                'ger1': gerente1, 
                'ger2': gerente2, 
                'ger3': gerente3, 
                'id': id
            })
            
            # Confirmar los cambios
            conn.commit()
            conn.close()
            
            # Respuesta exitosa
            return jsonify({'success': True, 'message': 'Usuario actualizado correctamente'})
        except Exception as e:
            # En caso de error
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# Configuración de la carpeta de carga
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


#################################################Tour de presentacion de la APP####################################################



# Configurar logging para mejor depuración
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



# Asegurarnos de que la carpeta static existe
if not os.path.exists('static'):
    os.makedirs('static')
    logger.info("Directorio 'static' creado")

# Asegurarnos de que el directorio templates existe
if not os.path.exists('templates'):
    os.makedirs('templates')
    logger.info("Directorio 'templates' creado")

@app.route('/presentacion')
def mostrar_presentacion():
    # Ruta a la carpeta donde se encuentra la presentación
    pptx_name = "Manual_CierreFarmacias"  # Nombre de la presentación sin extensión
    
    # Directorio donde deberían estar las imágenes
    presentation_dir = os.path.join(app.static_folder, 'presentaciones', pptx_name)
    
    # Verificar si el directorio existe
    if not os.path.exists(presentation_dir):
        logger.error(f"Directorio no encontrado: {presentation_dir}")
        return f"Error: El directorio {presentation_dir} no existe. Asegúrate de que las imágenes estén en esta ubicación."
    
    try:
        # Buscar todas las imágenes existentes en el directorio
        image_files = [f for f in os.listdir(presentation_dir) 
                      if f.endswith('.png') or f.endswith('.jpg') or f.endswith('.jpeg')]
        
        # Ordenar las imágenes por su número de diapositiva
        # Asume formato "slide_X.png" o similar
        image_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]) 
                        if '_' in x and x.split('_')[1].split('.')[0].isdigit() 
                        else float('inf'))
        
        if not image_files:
            logger.warning(f"No se encontraron imágenes en {presentation_dir}")
            
        logger.info(f"Encontradas {len(image_files)} imágenes en {presentation_dir}")
        logger.debug(f"Imágenes encontradas: {image_files}")
        
        return render_template('presentacion.html', 
                               presentacion=pptx_name, 
                               imagenes=image_files)
    except Exception as e:
        logger.exception("Error al procesar las imágenes")
        return f"Error al procesar las imágenes: {str(e)}"

@app.route('/check_files')
def check_files():
    """Ruta de depuración para verificar si los archivos existen"""
    static_dir = app.static_folder
    presentaciones_dir = os.path.join(static_dir, 'presentaciones')
    
    result = {
        'static_folder': static_dir,
        'static_folder_exists': os.path.exists(static_dir),
        'presentaciones_dir': presentaciones_dir,
        'presentaciones_dir_exists': os.path.exists(presentaciones_dir)
    }
    
    # Si el directorio de presentaciones existe, listar su contenido
    if os.path.exists(presentaciones_dir):
        presentation_dirs = os.listdir(presentaciones_dir)
        result['presentation_dirs'] = presentation_dirs
        
        for pres_dir in presentation_dirs:
            full_pres_dir = os.path.join(presentaciones_dir, pres_dir)
            if os.path.isdir(full_pres_dir):
                result[f'files_in_{pres_dir}'] = os.listdir(full_pres_dir)
    
    return jsonify(result)

# Crear o actualizar el archivo presentacion.html
#with open('templates/presentacion.html', 'w') as f:
with open('templates/presentacion.html', 'w', encoding='utf-8') as f:
    f.write("""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tour App de Cierre de Farmacias</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #0d47a1 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .container-main {
            width: 95%;
            max-width: 1400px;
            margin: 30px auto;
        }
        
        .header-section {
            margin-bottom: 25px;
        }
        
        .title-main {
            color: #0d47a1;
            font-weight: 600;
            margin-bottom: 20px;
            border-left: 5px solid #0d47a1;
            padding-left: 15px;
        }
        
        .slideshow-container {
            position: relative;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            overflow: hidden;
            margin-bottom: 30px;
        }
        
        .control-panel {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #0d47a1;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        
        .nav-button {
            background: #fff;
            color: #0d47a1;
            border: none;
            padding: 10px 20px;
            cursor: pointer;
            border-radius: 4px;
            font-weight: 600;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .nav-button:hover {
            background: #e9ecef;
            transform: translateY(-2px);
        }
        
        .page-counter {
            color: white;
            font-weight: bold;
            font-size: 16px;
            background: rgba(255,255,255,0.2);
            padding: 8px 15px;
            border-radius: 20px;
        }
        
        .slide-content {
            display: none;
            text-align: center;
            padding: 30px;
        }
        
        .slide-content.active {
            display: block;
            animation: fadeIn 0.5s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .slide-content img {
            max-width: 100%;
            max-height: 75vh;
            object-fit: contain;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .embed-section {
            margin-top: 30px;
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .embed-title {
            font-size: 18px;
            font-weight: 600;
            color: #0d47a1;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .embed-container {
            width: 100%;
            height: 600px;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .embed-container iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        .footer {
            text-align: center;
            padding: 20px 0;
            margin-top: 30px;
            color: #6c757d;
            font-size: 14px;
            border-top: 1px solid #e0e0e0;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .container-main {
                width: 100%;
                padding: 0 15px;
            }
            
            .slide-content {
                padding: 15px;
            }
            
            .embed-container {
                height: 400px;
            }
            
            .nav-button {
                padding: 8px 12px;
                font-size: 14px;
            }
        }
    </style>
</head>
<body>
    <!-- Barra de navegación -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-book-open me-2"></i>
               Tour App de Cierre de Farmacias
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('dashboard') }}">Inicio</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="{{ url_for('aplicacion') }}">App Cierre Farmacias</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="{{ url_for('upload_file') }}">Subir archivo</a>
                    </li>
                </ul>
                <ul class="navbar-nav">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="navbarDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                            Bienvenido, {{ nombre }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="navbarDropdown">
                            <li><a class="dropdown-item" href="{{ url_for('logout') }}">Cerrar Sesión</a></li>
                        </ul>
                    </li>
                </ul>
                           
                
                
                
                
            </div>
        </div>
    </nav>

    <!-- Contenido principal -->
    <div class="container-main">
        <div class="header-section">
            <h1 class="title-main">
                <i class="fas fa-store me-2"></i>
                Tour App de Cierre de Farmacias
            </h1>
        </div>

        <!-- Visualizador de diapositivas -->
        <div class="slideshow-container">
            <div class="control-panel">
                <button class="nav-button" onclick="changeSlide(-1)">
                    <i class="fas fa-chevron-left"></i> Anterior
                </button>
                <span class="page-counter">
                    <i class="fas fa-file-powerpoint me-2"></i>
                    Diapositiva <span id="current">1</span> de <span id="total">{{ imagenes|length }}</span>
                </span>
                <button class="nav-button" onclick="changeSlide(1)">
                    Siguiente <i class="fas fa-chevron-right"></i>
                </button>
            </div>
            
            <div class="slides-container">
                {% for img in imagenes %}
                <div class="slide-content {% if loop.first %}active{% endif %}">
                    <img src="{{ url_for('static', filename='presentaciones/' + presentacion + '/' + img) }}" 
                         alt="Diapositiva {{ loop.index }}" 
                         class="img-fluid">
                </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- Sección de PowerPoint embebido -->
        <div class="embed-section">
            <div class="embed-title">
                <i class="fas fa-external-link-alt"></i>
                Versión interactiva del documento
            </div>
            <div class="embed-container">
                <iframe src="https://walgreens-my.sharepoint.com/:p:/r/personal/hugo_ibarra_benavides_com_mx/_layouts/15/Doc.aspx?sourcedoc=%7B838A5CE6-E03B-47C0-BDED-CD726A83FF00%7D&file=Manual_CierreFarmacias.pptx&wdLOR=c5FFB0F54-D183-435E-93DE-A2F5F5311A5F&fromShare=true&action=edit&mobileredirect=true" 
                        frameborder="0" 
                        scrolling="no" 
                        allowfullscreen></iframe>
            </div>
        </div>
    </div>
    
    <!-- Pie de página -->
    <div class="footer">
        <p>&copy; 2025 Febrero - Farmacia Benavides. Todos los derechos reservados.</p>
    </div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let slideIndex = 0;
        const slides = document.getElementsByClassName("slide-content");
        const totalSlides = slides.length;
        document.getElementById("total").textContent = totalSlides;
        
        function showSlide(n) {
            if (totalSlides === 0) return;
            
            if (n >= totalSlides) {slideIndex = 0}    
            if (n < 0) {slideIndex = totalSlides - 1}
            
            for (let i = 0; i < totalSlides; i++) {
                slides[i].classList.remove("active");
            }
            
            slides[slideIndex].classList.add("active");
            document.getElementById("current").textContent = slideIndex + 1;
        }
        
        function changeSlide(n) {
            slideIndex += n;
            showSlide(slideIndex);
        }
        
        // Verificar si las imágenes se cargan correctamente
        window.addEventListener('load', function() {
            const images = document.querySelectorAll('.slide-content img');
            images.forEach(img => {
                img.addEventListener('error', function() {
                    this.style.display = 'none';
                    const errorMsg = document.createElement('div');
                    errorMsg.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>Error al cargar esta imagen.</div>';
                    this.parentNode.appendChild(errorMsg);
                });
            });
        });
        
        // Soporte para navegar con teclado
        document.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft') {
                changeSlide(-1);
            } else if (e.key === 'ArrowRight') {
                changeSlide(1);
            }
        });
    </script>
</body>
</html>
    """)



#########################################################################################################################
# if __name__ == '__main__':
    #   app.run(debug=True)


if __name__ == '__main__':
           app.run(debug=True, port=5020, host='10.30.43.103')







































































