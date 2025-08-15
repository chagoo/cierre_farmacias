from sqlalchemy import func
from ..models import CierreSucursal


def fetch_data(db):
    """Return aggregated counts per departamento and action."""

    result = (
        db.session.query(
            CierreSucursal.departamento,
            func.count().label("cont"),
            CierreSucursal.accion,
        )
        .filter(CierreSucursal.departamento != "BAJA DIRECTA")
        .group_by(CierreSucursal.departamento, CierreSucursal.accion)
        .all()
    )
    return [["Departamento", "Cantidad", "Accion"]] + [list(row) for row in result]


def fetch_summary(db):
    """Return total counts per departamento."""

    result = (
        db.session.query(
            CierreSucursal.departamento,
            func.count().label("total"),
        )
        .filter(CierreSucursal.departamento != "BAJA DIRECTA")
        .group_by(CierreSucursal.departamento)
        .all()
    )
    return [["Departamento", "Total"]] + [list(row) for row in result]
