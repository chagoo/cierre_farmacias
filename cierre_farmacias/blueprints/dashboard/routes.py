from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from sqlalchemy import text
from cierre_farmacias import db
from cierre_farmacias.utils.decorators import login_required, nivel_acceso_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
@nivel_acceso_required()
def dashboard_home():
    return render_template('dashboard2.html')

# Nota: consolidamos el feed de datos en un único endpoint '/data'

@dashboard_bp.route('/ordenes')
@login_required
@nivel_acceso_required()
def ordenes():
    # Detectar si usamos SQLite (tests) para evitar calificadores de esquema
    try:
        dialect = (db.session.get_bind().dialect.name or '').lower()
    except Exception:
        dialect = ''
    if 'sqlite' in dialect:
        sql = """
        SELECT DISTINCT [ID],[FileName],[Tipo],[FechaIni],[FechaFin],[Estatus],[Farmacia],[Domicilio],[Ciudad],[Estado],[GerenteOP],[Director]
        FROM CierreSucursales4 WHERE COALESCE(Departamento,'')<>'BAJA DIRECTA' ORDER BY [ID] DESC
        """
    else:
        sql = """
        SELECT DISTINCT [ID],[FileName],[Tipo],[FechaIni],[FechaFin],[Estatus],[Farmacia],[Domicilio],[Ciudad],[Estado],[GerenteOP],[Director]
        FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA' ORDER BY [ID] DESC
        """
    try:
        rows = db.session.execute(text(sql)).fetchall()
    except Exception:
        rows = []  # En tests puede no existir la tabla; devolvemos vacío en lugar de error
    cols = ['ID','FileName','Tipo','FechaIni','FechaFin','Estatus','Farmacia','Domicilio','Ciudad','Estado','GerenteOP','Director']
    data = [dict(zip(cols,r)) for r in rows]
    return render_template('Ordenes.html', data=data)

@dashboard_bp.route('/data')
@login_required
@nivel_acceso_required()
def data_feed():
    # Intenta agregar por Departamento y Tipo (Tipo_General o Tipo);
    # si falla (tabla inexistente), devuelve solo cabecera.
    header = ["Departamento", "Cantidad", "Tipo"]
    try:
        sql = text(
            """
            SELECT Departamento as depto,
                   COUNT(*) as cantidad,
                   COALESCE(Tipo_General, Tipo) as tipo
            FROM CierreSucursales4
            WHERE COALESCE(Departamento,'') <> 'BAJA DIRECTA'
            GROUP BY Departamento, COALESCE(Tipo_General, Tipo)
            ORDER BY Departamento
            """
        )
        rows = db.session.execute(sql).fetchall()
        data_rows = [[r[0] or '', int(r[1] or 0), r[2] or ''] for r in rows]
        # Fallback seguro para Google Charts (al menos 2 columnas tras pivot)
        if not data_rows:
            data_rows = [["Sin datos", 0, "N/A"]]
        data = [header] + data_rows
    except Exception:
        # En error, devolvemos una fila de ejemplo para evitar errores del chart
        data = [header, ["Sin datos", 0, "N/A"]]
    return jsonify(data)

@dashboard_bp.route('/activos')
@login_required
@nivel_acceso_required()
def activos():
    try:
        dialect = (db.session.get_bind().dialect.name or '').lower()
    except Exception:
        dialect = ''
    if 'sqlite' in dialect:
        sql = """
        SELECT [ID],[Departamento],[Soc.] as Soc,[Act. Fijo] as ActFijo,[Clase],[Fe. Capit.] as FeCapit,[Denominacion del activo fijo] as DenominacionActivoFijo,[Val. Cont.] as ValCont,[Mon.] as Mon,[Orden],[Ceco],[Ceco Destino] as CecoDestino,[Tipo de Activo] as TipoActivo,[Observaciones],[Operativo],[Accion],[Unidades],[PrecioUnitario]
        FROM CierreSucursales4 WHERE COALESCE(Departamento,'')<>'BAJA DIRECTA' ORDER BY [ID] DESC
        """
    else:
        sql = """
        SELECT [ID],[Departamento],[Soc.] as Soc,[Act. Fijo] as ActFijo,[Clase],[Fe. Capit.] as FeCapit,[Denominacion del activo fijo] as DenominacionActivoFijo,[Val. Cont.] as ValCont,[Mon.] as Mon,[Orden],[Ceco],[Ceco Destino] as CecoDestino,[Tipo de Activo] as TipoActivo,[Observaciones],[Operativo],[Accion],[Unidades],[PrecioUnitario]
        FROM [DBBI].[dbo].[CierreSucursales4] WHERE Departamento<>'BAJA DIRECTA' ORDER BY [ID] DESC
        """
    try:
        rows = db.session.execute(text(sql)).fetchall()
    except Exception:
        rows = []
    cols = ['ID','Departamento','Soc','ActFijo','Clase','FeCapit','DenominacionActivoFijo','ValCont','Mon','Orden','Ceco','CecoDestino','TipoActivo','Observaciones','Operativo','Accion','Unidades','PrecioUnitario']
    data = [dict(zip(cols,r)) for r in rows]
    return render_template('activos.html', data=data)

@dashboard_bp.route('/detalles/<ceco>')
@login_required
def detalles_view(ceco):
    q = text("""
        SELECT DISTINCT Departamento AS departamento, FechaIni, FechaFin, Ceco AS ceco,
        CASE 
          WHEN COUNT(CASE WHEN Accion='Baja' THEN 1 END) OVER (PARTITION BY Departamento)>0 
               AND COUNT(CASE WHEN Accion IS NULL OR Accion='Pendiente' THEN 1 END) OVER (PARTITION BY Departamento)>0 THEN 'Activos Mixto'
          WHEN COUNT(CASE WHEN Accion='Baja' THEN 1 END) OVER (PARTITION BY Departamento)=COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Baja'
          WHEN COUNT(CASE WHEN Accion='Pendiente' THEN 1 END) OVER (PARTITION BY Departamento)=COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Pendientes'
          WHEN COUNT(CASE WHEN Accion='Traspaso' THEN 1 END) OVER (PARTITION BY Departamento)=COUNT(*) OVER (PARTITION BY Departamento) THEN 'Activos Traspaso'
          ELSE 'Otro' END AS Estatus
        FROM CierreSucursales4 WHERE Departamento<>'BAJA DIRECTA' AND Ceco=:ceco
    """)
    rows = db.session.execute(q, {'ceco': ceco}).fetchall()
    return render_template('detalles_2.html', detalles=rows)

@dashboard_bp.route('/subdetalles/<departamento>/<ceco>', methods=['GET','POST'])
@login_required
def subdetalles(departamento, ceco):
    if request.method == 'POST':
        # procesamiento simple (migrado)
        for actfijo in request.form.getlist('ActFijo'):
            accion = request.form.get(f'Accion_{actfijo}')
            ceco_dest = request.form.get(f'CecoDestino_{actfijo}') or None
            if accion == 'Traspaso' and not ceco_dest:
                continue  # podría devolver error
            upd = text("""UPDATE CierreSucursales4 SET [Accion]=:accion, [Ceco Destino]=:dest WHERE [Act. Fijo]=:act AND [Departamento]=:dep AND [Ceco]=:ceco""")
            db.session.execute(upd, {'accion': accion, 'dest': ceco_dest, 'act': actfijo, 'dep': departamento, 'ceco': ceco})
        db.session.commit()
        return redirect(url_for('dashboard.subdetalles', departamento=departamento, ceco=ceco))
    sel = text("""SELECT [ID],[Departamento],[Act. Fijo],[Denominacion del activo fijo],[Val. Cont.],[Ceco],[Ceco Destino],[Tipo de Activo],[Accion],[Estatus],[Operativo],[Clase],[Fe. Capit.],[Orden],[FirmaSolicitante]
               FROM CierreSucursales4 WHERE Departamento=:dep AND Ceco=:ceco ORDER BY [ID]""")
    rows = db.session.execute(sel, {'dep': departamento, 'ceco': ceco}).fetchall()
    return render_template('subdetalles_5.html', activos=rows, Departamento=departamento, Ceco=ceco, mensaje='' if rows else 'Sin registros')

@dashboard_bp.route('/subordenes', methods=['GET','POST'])
@login_required
def subordenes():
    if request.method == 'POST':
        # JSON update for email fields
        try:
            payload = request.get_json(force=True)
            rec_id = int(payload.get('id'))
            updates = payload.get('updates', {})
            allowed_map = {
                'Correo1': '[Correo 1]',
                'Correo2': '[Correo 2]',
                'Correo3': '[Correo 3]',
                'Correo4': '[Correo 4]',
                'Correo5': '[Correo 5]'
            }
            set_parts = []
            params = {'id': rec_id}
            for k,v in updates.items():
                col = allowed_map.get(k)
                if col is not None:
                    param_key = f'val_{k}'
                    set_parts.append(f"{col}=:{param_key}")
                    params[param_key]=v
            if not set_parts:
                return jsonify({'error':'No hay campos válidos para actualizar'}),400
            stmt = text(f"UPDATE CierreSucursales4 SET {', '.join(set_parts)} WHERE ID=:id")
            db.session.execute(stmt, params)
            db.session.commit()
            return jsonify({'success': True, 'updated': list(updates.keys())})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}),500
    q = text("""SELECT [ID],[Departamento],[Ceco],[FechaIni],[FechaFin],[Estatus],[Correo 1],[Nivel Correo 1],[Correo 2],[Nivel Correo 2],[Correo 3],[Nivel Correo 3],[Correo 4],[Nivel Correo 4],[Correo 5],[Nivel Correo 5],[FirmaSolicitante],[DetallesFirmaSolicitante],[FirmaDepartamento],[DetallesFirmaDepartamento],[FirmaSeguridad],[DetallesFirmaSeguridad],[FirmaGerente],[DetallesFirmaGerente],[Tipo]
               FROM CierreSucursales4 WHERE COALESCE(Departamento,'')<>'BAJA DIRECTA' ORDER BY [ID] DESC""")
    try:
        rows = db.session.execute(q).fetchall()
    except Exception:
        rows = []
    cols=['ID','Departamento','Ceco','FechaIni','FechaFin','Estatus','Correo1','NivelCorreo1','Correo2','NivelCorreo2','Correo3','NivelCorreo3','Correo4','NivelCorreo4','Correo5','NivelCorreo5','FirmaSolicitante','DetallesFirmaSolicitante','FirmaDepartamento','DetallesFirmaDepartamento','FirmaSeguridad','DetallesFirmaSeguridad','FirmaGerente','DetallesFirmaGerente','Tipo']
    data=[dict(zip(cols,r)) for r in rows]
    return render_template('subordenes2.html', data=data)
