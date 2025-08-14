from flask import Blueprint, request, jsonify, render_template
import pandas as pd
from sqlalchemy import text
from cierre_farmacias import db
from cierre_farmacias.utils.decorators import login_required, nivel_acceso_required
from datetime import datetime
import os

uploads_bp = Blueprint('uploads', __name__)

EXPECTED_COLUMNS = [
    'Departamento','Soc.','Act. Fijo','Clase','Fe. Capit.','Denominacion del activo fijo','Val. Cont.','Mon.','Orden','Ceco','Ceco Destino','Tipo de Activo','Correo 1','Nivel Correo 1','Correo 2','Nivel Correo 2','Correo 3','Nivel Correo 3','Correo 4','Nivel Correo 4','Correo 5','Nivel Correo 5','Farmacia','Domicilio','Ciudad','Estado','GerenteOP','Director'
]

ALLOWED_EXT = {'xlsx','xls'}

def allowed_file(name: str):
    return '.' in name and name.rsplit('.',1)[1].lower() in ALLOWED_EXT

@uploads_bp.route('/upload', methods=['GET','POST'])
@login_required
@nivel_acceso_required()
def upload_file():
    if request.method=='POST':
        if 'file' not in request.files:
            return jsonify({'error':'Archivo faltante'}),400
        file = request.files['file']
        tipo_general = request.form.get('tipo_general')
        if file.filename == '':
            return jsonify({'error':'Nombre vacío'}),400
        if not tipo_general:
            return jsonify({'error':'Seleccione Tipo General'}),400
        if not allowed_file(file.filename):
            return jsonify({'error':'Extensión no permitida'}),400
        try:
            df = pd.read_excel(file)
            cols = df.columns.tolist()
            missing = [c for c in EXPECTED_COLUMNS if c not in cols]
            if missing:
                return jsonify({'error':'Columnas faltantes','missing':missing}),400
            filename_no_ext = os.path.splitext(file.filename)[0]
            df['FileName'] = filename_no_ext
            df['FechaIni'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df['Tipo_General'] = tipo_general
            df['Estatus_General'] = 'Iniciado'
            df['Accion'] = 'Pendiente'
            df.to_sql('CierreSucursales4', db.engine, if_exists='append', index=False, schema='dbo')
            # TODO: notificaciones (migrar lógica existente)
            return jsonify({'success':True,'rows':len(df)})
        except Exception as e:
            return jsonify({'error':str(e)}),500
    return render_template('index_excel_Monse5.html')
