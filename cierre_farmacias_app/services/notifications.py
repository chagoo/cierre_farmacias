from sqlalchemy import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_notification_email(ceco: str, departamento: str, db):
    """Send notification email for a given CECO and departamento."""
    query_contacts = text("""
        SELECT distinct
            cs4.[Correo 1] as correo1,
            cs4.[Correo 2] as correo2,
            cs4.[Correo 3] as correo3,
            cs4.[Correo 4] as correo4,
            cs4.[Correo 5] as correo5
        FROM [DBBI].[dbo].[CierreSucursales4] cs4
        WHERE cs4.[Ceco] = :ceco AND cs4.[Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
    """)

    with db.engine.connect() as conn:
        result = conn.execute(query_contacts, {"ceco": ceco, "departamento": departamento}).fetchone()

    if not result:
        return {"error": f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}"}

    if not isinstance(result, dict):
        result = dict(result._mapping)

    recipients = [result.get(key) for key in ['correo1', 'correo2', 'correo3', 'correo4', 'correo5'] if result.get(key)]

    if not recipients:
        return {"error": "No hay correos electrónicos para enviar."}

    msg = MIMEMultipart()
    msg['Subject'] = f'Notificación para CECO {ceco}'
    msg['From'] = 'no-reply@example.com'
    msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(f'Se ha cargado información para el departamento {departamento} y CECO {ceco}.', 'plain'))

    try:
        with smtplib.SMTP('localhost') as server:
            server.sendmail(msg['From'], recipients, msg.as_string())
    except Exception as e:
        return {'error': str(e)}
    return {'success': True}
