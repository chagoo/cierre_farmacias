import os
from datetime import datetime
import pandas as pd
from ..utils.files import allowed_file

EXPECTED_COLUMNS = [
    'Departamento', 'Soc.', 'Act. Fijo', 'Clase', 'Fe. Capit.',
    'Denominacion del activo fijo', 'Val. Cont.', 'Mon.', 'Orden',
    'Ceco', 'Ceco Destino', 'Tipo de Activo', 'Correo 1',
    'Nivel Correo 1', 'Correo 2', 'Nivel Correo 2', 'Correo 3',
    'Nivel Correo 3', 'Correo 4', 'Nivel Correo 4', 'Correo 5',
    'Nivel Correo 5', 'Farmacia', 'Domicilio', 'Ciudad', 'Estado',
    'GerenteOP', 'Director'
]

def process_upload(file, tipo_general: str, db):
    """Read the Excel file, validate columns and insert into DB."""
    df = pd.read_excel(file)

    excel_columns = df.columns.tolist()
    missing_columns = [col for col in EXPECTED_COLUMNS if col not in excel_columns]
    if missing_columns:
        raise ValueError(f'Las columnas del archivo no coinciden: {missing_columns}')

    if 'Estatus_General' in df.columns:
        if any(df['Estatus_General'].astype(str).str.strip() == 'Iniciado') and not tipo_general:
            raise ValueError('Debe seleccionar un Tipo General cuando el Estatus es "Iniciado"')

    filename_without_ext = os.path.splitext(file.filename)[0]
    current_date = datetime.now().strftime("%d %B %Y")
    estatus_general = 'Iniciado'
    accion = 'Pendiente'

    df['FileName'] = filename_without_ext
    df['FechaIni'] = current_date
    df['Tipo_General'] = tipo_general
    df['Estatus_General'] = estatus_general
    df['Accion'] = accion

    df.to_sql('CierreSucursales4', db.engine, if_exists='append', index=False, schema='dbo')
    return df
