from sqlalchemy import text


def fetch_data(db):
    query = text("""
        SELECT Departamento, SUM(cont) AS cont, Accion
        FROM (
            SELECT Departamento, Accion, COUNT(*) AS cont
            FROM DBBI.dbo.CierreSucursales4
            WHERE Departamento <> 'BAJA DIRECTA'
            GROUP BY Departamento, Accion
        ) AS subquery
        GROUP BY Departamento, Accion
    """)
    result = db.session.execute(query)
    return [["Departamento", "Cantidad", "Accion"]] + [list(row) for row in result]


def fetch_summary(db):
    query = text("""
        SELECT Departamento, SUM(cont) AS total
        FROM (
            SELECT Departamento, Accion, COUNT(*) AS cont
            FROM DBBI.dbo.CierreSucursales4
            WHERE Departamento <> 'BAJA DIRECTA'
            GROUP BY Departamento, Accion
        ) AS subquery
        GROUP BY Departamento
    """)
    result = db.session.execute(query)
    return [["Departamento", "Total"]] + [list(row) for row in result]
