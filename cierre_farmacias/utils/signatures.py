from sqlalchemy import text
from datetime import datetime, date
from cierre_farmacias import db
from cierre_farmacias.utils.notifications import send_flow_notification

def _is_sqlite():
    try:
        bind = db.session.get_bind()
        name = getattr(getattr(bind, 'dialect', None), 'name', '') or getattr(bind, 'name', '')
        return 'sqlite' in (name or '').lower()
    except Exception:
        return False

def _tbl(name: str) -> str:
    # Use fully qualified names only for MSSQL; SQLite lacks database/schema
    if _is_sqlite():
        return name
    return f"[DBBI].[dbo].[{name}]"

def _sig_select():
    return text(f"""
 SELECT distinct c.[Correo 1], c.[Correo 2], c.[Correo 3], c.[Correo 4], c.[Correo 5],
        g.[Seguridad1], g.[Seguridad2], g.[Seguridad3], g.[Gerente1], g.[Gerente2], g.[Gerente3],
        c.[FirmaSolicitante], c.[DetallesFirmaSolicitante],
        c.[FirmaDepartamento], c.[DetallesFirmaDepartamento],
        c.[FirmaSeguridad], c.[DetallesFirmaSeguridad],
        c.[FirmaGerente], c.[DetallesFirmaGerente], c.[FechaFin]
 FROM {_tbl('CierreSucursales4')} c
 CROSS JOIN {_tbl('CierreSucursales_Gerentes')} g
 WHERE c.[Ceco]=:ceco AND c.[Departamento]=:dep
""")

def _update_template(sets: str) -> str:
    return f"""
UPDATE {_tbl('CierreSucursales4')}
SET {sets}
WHERE [Ceco]=:ceco AND [Departamento]=:dep
"""

ORDER_FLOW = ['solicitante','departamento','seguridad','gerente']

class SignatureState:
    def __init__(self, row: tuple):
        (self.correo1,self.correo2,self.correo3,self.correo4,self.correo5,
         self.seg1,self.seg2,self.seg3,self.ger1,self.ger2,self.ger3,
         self.firma_solicitante,self.det_solicitante,
         self.firma_departamento,self.det_departamento,
         self.firma_seguridad,self.det_seguridad,
         self.firma_gerente,self.det_gerente,self.fecha_fin) = row

    def normalize(self):
        def norm(v):
            return v.lower().strip() if isinstance(v,str) else ''
        self.correo1 = norm(self.correo1)
        self.correo2 = norm(self.correo2)
        self.correo3 = norm(self.correo3)
        self.correo4 = norm(self.correo4)
        self.correo5 = norm(self.correo5)
        self.seg1 = norm(self.seg1)
        self.seg2 = norm(self.seg2)
        self.seg3 = norm(self.seg3)
        self.ger1 = norm(self.ger1)
        self.ger2 = norm(self.ger2)
        self.ger3 = norm(self.ger3)
        return self

    def can_sign(self, email: str):
        e = email.lower().strip()
        can = {
          'solicitante': ((e in {self.correo1,self.correo2,self.correo3}) and self.firma_solicitante!='Verdadero'),
          'departamento': ((e in {self.correo4,self.correo5}) and self.firma_solicitante=='Verdadero' and self.firma_departamento!='Verdadero'),
          'seguridad': ((e in {self.seg1,self.seg2,self.seg3}) and self.firma_solicitante=='Verdadero' and self.firma_departamento=='Verdadero' and self.firma_seguridad!='Verdadero'),
          'gerente': ((e in {self.ger1,self.ger2,self.ger3}) and self.firma_solicitante=='Verdadero' and self.firma_departamento=='Verdadero' and self.firma_seguridad=='Verdadero' and self.firma_gerente!='Verdadero')
        }
        return can

    def as_dict(self):
        return self.__dict__


def load_signature_state(ceco:str, dep:str) -> SignatureState|None:
    try:
        with db.engine.connect() as conn:
            row = conn.execute(_sig_select(), {'ceco': ceco, 'dep': dep}).fetchone()
    except Exception:
        row = None
    if not row: return None
    return SignatureState(row).normalize()


def update_signatures(ceco:str, dep:str, user_email:str, form_data:dict):
    state = load_signature_state(ceco, dep)
    if not state:
        return {'error':'No existe registro de firmas'}
    can = state.can_sign(user_email)

    sets = []
    params = {'ceco': ceco, 'dep': dep}
    next_stage = None
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def handle(role, field_flag, field_detail):
        nonlocal next_stage
        val = form_data.get(role)
        if not val: return
        if not can[role]:
            return
        logical = 'Verdadero' if val == 'si' else 'Falso'
        sets.append(f"{field_flag} = :{field_flag}")
        params[field_flag] = logical
        sets.append(f"{field_detail} = :{field_detail}")
        params[field_detail] = f"{user_email} - {timestamp}"
        if logical=='Verdadero':
            if role=='solicitante':
                next_stage = 'solicitante_to_departamento'
            elif role=='departamento':
                next_stage = 'departamento_to_seguridad'
            elif role=='seguridad':
                next_stage = 'seguridad_to_gerencia'
            elif role=='gerente':
                # cierre
                sets.append("[FechaFin] = :fecha_fin")
                params['fecha_fin'] = date.today().strftime('%Y-%m-%d')

    handle('solicitante','[FirmaSolicitante]','[DetallesFirmaSolicitante]')
    handle('departamento','[FirmaDepartamento]','[DetallesFirmaDepartamento]')
    handle('seguridad','[FirmaSeguridad]','[DetallesFirmaSeguridad]')
    handle('gerente','[FirmaGerente]','[DetallesFirmaGerente]')

    if not sets:
        return {'message':'Sin cambios'}

    sql = text(_update_template(','.join(sets)))
    with db.engine.begin() as conn:
        conn.execute(sql, params)

    notification = None
    if next_stage:
        notification = send_flow_notification(ceco, dep, next_stage)
    return {'updated': True, 'next_stage': next_stage, 'notification': notification}
