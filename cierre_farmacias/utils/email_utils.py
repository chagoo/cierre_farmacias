from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from typing import List
from flask import current_app

def build_html_table(rows: List[dict], columns: List[str]) -> str:
    thead = ''.join(f'<th>{col}</th>' for col in columns)
    trs = []
    for r in rows:
        tds = ''.join(f'<td>{r.get(col, "")}</td>' for col in columns)
        trs.append(f'<tr>{tds}</tr>')
    return f'<table border="1" cellpadding="5" cellspacing="0"><tr>{thead}</tr>' + ''.join(trs) + '</table>'


def send_email(subject: str, body_html: str, to: List[str], cc: List[str] | None = None):
    if not to:
        raise ValueError('Lista TO vacía')
    msg = MIMEMultipart()
    sender = current_app.config.get('SMTP_SENDER', 'no-reply@example.com')
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    if cc:
        msg['Cc'] = ', '.join(cc)
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))
    all_rcpts = to + (cc or [])
    smtp_server = current_app.config.get('SMTP_SERVER', 'localhost')
    smtp_port = int(current_app.config.get('SMTP_PORT', 25))
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.sendmail(sender, all_rcpts, msg.as_string())
    return {'sent': True, 'to': to, 'cc': cc or []}
