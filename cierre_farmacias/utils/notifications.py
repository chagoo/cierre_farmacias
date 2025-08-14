from cierre_farmacias.utils.query_helpers import fetch_contacts, fetch_assets_for_email
from cierre_farmacias.utils.email_utils import build_html_table, send_email

ASSET_COLUMNS = ['Departamento','Act. Fijo','Clase','Denominacion del activo fijo','Orden','Ceco','Farmacia','FechaIni']

FLOW_MAP = {
    'initial': {
        'to': ['correo1','correo2','correo3'],
        'cc': ['correo4','correo5','seguridad1','seguridad2','seguridad3','gerente1','gerente2','gerente3'],
        'subject': 'Se requiere de su Firma electrónica Solicitante'
    },
    'solicitante_to_departamento': {
        'to': ['correo4','correo5'],
        'cc': ['correo1','correo2','correo3','seguridad1','seguridad2','seguridad3','gerente1','gerente2','gerente3'],
        'subject': 'Se requiere de su Firma electrónica Departamento'
    },
    'departamento_to_seguridad': {
        'to': ['seguridad1','seguridad2','seguridad3'],
        'cc': ['correo1','correo2','correo3','correo4','correo5','gerente1','gerente2','gerente3'],
        'subject': 'Se requiere de su Firma electrónica Seguridad'
    },
    'seguridad_to_gerencia': {
        'to': ['gerente1','gerente2','gerente3'],
        'cc': ['correo1','correo2','correo3','correo4','correo5','seguridad1','seguridad2','seguridad3'],
        'subject': 'Se requiere de su Firma electrónica Gerencia'
    }
}

def _collect(fields, data):
    emails = []
    for f in fields:
        v = data.get(f)
        if v and v != 'None':
            emails.append(v)
    return emails

def send_flow_notification(ceco: str, departamento: str, stage: str):
    contacts = fetch_contacts(ceco, departamento)
    if not contacts:
        return {'error':'Sin contactos'}
    assets = fetch_assets_for_email(ceco, departamento)
    if not assets:
        return {'error':'Sin activos'}
    cfg = FLOW_MAP.get(stage)
    if not cfg:
        return {'error':'Etapa desconocida'}
    to_emails = _collect(cfg['to'], contacts)
    cc_emails = _collect(cfg['cc'], contacts)
    if not to_emails:
        return {'error':'Sin destinatarios to'}
    table = build_html_table(assets, ASSET_COLUMNS)
    body = f"<p>Buen día. Se requiere su firma electrónica.</p>{table}<p>Acceso: http://10.30.43.103:5020/</p>"
    subj = f"{cfg['subject']} - CECO: {ceco}, Departamento: {departamento}"
    result = send_email(subj, body, to_emails, cc_emails)
    return result
