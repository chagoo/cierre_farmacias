from sqlalchemy import create_engine, text
from openpyxl import load_workbook
import win32com.client
import os
from datetime import datetime

import os
DB_SERVER = os.getenv('DB_SERVER', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'DBBI')
DB_USER = os.getenv('DB_USER', 'sa')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_TABLE = 'CierreSucursales4'


def get_data_from_sql(departamento, ceco):
    SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"
    engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=False)
    query = text(f"""
    SELECT [Act. Fijo],  Unidades, [Denominacion del activo fijo], [Ceco] as CecoOrigen, [Ceco Destino] as CecoDestino, 
           [Val. Cont.] as ValorUnitario,  [Mon.], Observaciones, [Operativo]
    FROM {DB_TABLE}
    WHERE [Ceco]=:ceco AND [Departamento]=:departamento AND [Accion]='Traspaso';
    """)
    with engine.connect() as connection:
        result = connection.execute(query, {"ceco": ceco, "departamento": departamento})
        return result.fetchall()


def actualizar_excel_y_generar_pdf(ruta_excel, output_dir, departamento, ceco):
    ruta_temp = None
    excel = None
    try:
        datos = get_data_from_sql(departamento, ceco)
        if not datos:
            return
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        ruta_pdf = os.path.join(output_dir, f"solicitud_traspaso_tabla_{departamento}_{ceco}.pdf")
        ruta_temp = ruta_excel.replace('.xlsx', '_temp.xlsx')
        wb = load_workbook(filename=ruta_excel)
        sheet = wb.active
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        sheet['K4'] = fecha_actual
        for i, row in enumerate(datos):
            if i >= 24:
                break
            fila_actual = 10 + i
            sheet[f'B{fila_actual}'] = row[0]
            sheet[f'C{fila_actual}'] = row[1]
            sheet[f'D{fila_actual}'] = row[2]
            sheet[f'F{fila_actual}'] = row[3]
            sheet[f'G{fila_actual}'] = row[4]
            sheet[f'H{fila_actual}'] = row[5]
            sheet[f'I{fila_actual}'] = row[6]
            sheet[f'J{fila_actual}'] = row[7]
            operativo = row[8]
            if operativo == "Operativo":
                sheet[f'K{fila_actual}'] = "X"
                sheet[f'L{fila_actual}'] = ""
            elif operativo == "No Operativo":
                sheet[f'K{fila_actual}'] = ""
                sheet[f'L{fila_actual}'] = "X"
            else:
                sheet[f'K{fila_actual}'] = ""
                sheet[f'L{fila_actual}'] = ""
        wb.save(ruta_temp)
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(os.path.abspath(ruta_temp))
        active_sheet = wb.ActiveSheet
        active_sheet.ExportAsFixedFormat(0, os.path.abspath(ruta_pdf))
        wb.Close(SaveChanges=False)
        excel.Quit()
        excel = None
    finally:
        if ruta_temp and os.path.exists(ruta_temp):
            try:
                os.remove(ruta_temp)
            except Exception:
                pass
        if excel:
            try:
                excel.Quit()
            except Exception:
                pass
