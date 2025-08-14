from sqlalchemy import text
from cierre_farmacias import db

def _is_sqlite():
    try:
        bind = db.session.get_bind()
        name = getattr(getattr(bind, 'dialect', None), 'name', '') or getattr(bind, 'name', '')
        return 'sqlite' in (name or '').lower()
    except Exception:
        return False

def _tbl(name: str) -> str:
    if _is_sqlite():
        return name
    return f"[DBBI].[dbo].[{name}]"

def fetch_contacts(ceco: str, departamento: str):
    q = text(f"""
        SELECT distinct
            cs4.[Correo 1] as correo1,
            cs4.[Correo 2] as correo2,
            cs4.[Correo 3] as correo3,
            cs4.[Correo 4] as correo4,
            cs4.[Correo 5] as correo5,
            g.[Seguridad1] as seguridad1,
            g.[Seguridad2] as seguridad2,
            g.[Seguridad3] as seguridad3,
            g.[Gerente1]  as gerente1,
            g.[Gerente2]  as gerente2,
            g.[Gerente3]  as gerente3
        FROM {_tbl('CierreSucursales4')} cs4
        CROSS JOIN {_tbl('CierreSucursales_Gerentes')} g
        WHERE cs4.[Ceco]=:ceco AND cs4.[Departamento]=:dep AND cs4.[Departamento]<>'BAJA DIRECTA'
    """)
    with db.engine.connect() as conn:
        row = conn.execute(q, {'ceco': ceco, 'dep': departamento}).fetchone()
    if not row:
        return None
    return dict(row._mapping)

def fetch_assets_for_email(ceco: str, departamento: str):
    q = text(f"""
        SELECT distinct [Departamento],[Act. Fijo],[Clase],[Denominacion del activo fijo],[Orden],[Ceco],[Farmacia],[FechaIni]
        FROM {_tbl('CierreSucursales4')}
        WHERE [Ceco]=:ceco AND [Departamento]=:dep AND [Departamento]<>'BAJA DIRECTA'
    """)
    with db.engine.connect() as conn:
        rows = conn.execute(q, {'ceco': ceco, 'dep': departamento}).fetchall()
    return [dict(r._mapping) for r in rows]
