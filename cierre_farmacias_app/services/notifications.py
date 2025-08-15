from sqlalchemy import text
from flask import render_template
from flask_mail import Message
from flask_babel import gettext as _
from ..extensions import mail, celery


def send_notification_email(ceco: str, departamento: str, db):
    """Queue notification email for a given CECO and departamento."""
    query_contacts = text(
        """
        SELECT distinct
            cs4.[Correo 1] as correo1,
            cs4.[Correo 2] as correo2,
            cs4.[Correo 3] as correo3,
            cs4.[Correo 4] as correo4,
            cs4.[Correo 5] as correo5
        FROM [DBBI].[dbo].[CierreSucursales4] cs4
        WHERE cs4.[Ceco] = :ceco AND cs4.[Departamento] = :departamento and Departamento<>'BAJA DIRECTA'
        """
    )

    with db.engine.connect() as conn:
        result = conn.execute(query_contacts, {"ceco": ceco, "departamento": departamento}).fetchone()

    if not result:
        return {"error": _(f"No se encontraron contactos para CECO: {ceco}, Departamento: {departamento}")}

    if not isinstance(result, dict):
        result = dict(result._mapping)

    recipients = [result.get(key) for key in ["correo1", "correo2", "correo3", "correo4", "correo5"] if result.get(key)]

    if not recipients:
        return {"error": _("No hay correos electrónicos para enviar.")}

    subject = _("Notificación para CECO %(ceco)s", ceco=ceco)
    context = {"departamento": departamento, "ceco": ceco}
    send_async_email.delay(subject, recipients, context)
    return {"success": True}


@celery.task
def send_async_email(subject: str, recipients: list[str], context: dict):
    msg = Message(subject=subject, recipients=recipients)
    msg.body = render_template("emails/notification.txt", **context)
    mail.send(msg)
