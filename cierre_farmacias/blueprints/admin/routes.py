from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import text
from cierre_farmacias import db
from cierre_farmacias.utils.decorators import login_required, nivel_acceso_required
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/accesos', methods=['GET','POST'])
@login_required
@nivel_acceso_required()
def accesos():
    if request.method=='POST':
        nombre = request.form.get('nombre')
        ap_pat = request.form.get('apellido_paterno')
        ap_mat = request.form.get('apellido_materno')
        password = request.form.get('password')
        hashed = generate_password_hash(password) if password else None
        departamento = request.form.get('departamento')
        nivel = request.form.get('nivel_acceso')
        correo = request.form.get('correo')
        usuario = correo.split('@')[0] if correo else None
        if not all([nombre, ap_pat, ap_mat, password, departamento, nivel, correo]):
            flash('Campos incompletos','danger')
            return redirect(url_for('admin.accesos'))
        try:
            with db.engine.begin() as conn:
                dup = conn.execute(text("SELECT 1 FROM CierreSucursales_Control_Accesos_Web WHERE Correo=:c"), {'c': correo}).fetchone()
                if dup:
                    flash('Correo ya registrado','danger')
                    return redirect(url_for('admin.accesos'))
                conn.execute(text("""
                    INSERT INTO CierreSucursales_Control_Accesos_Web ([Nombre],[Apellido Paterno],[Apellido Materno],[Usuario],[Password],[Departamento],[Nivel Acceso],[Correo])
                    VALUES (:n,:ap,:am,:u,:p,:d,:nivel,:c)
                """), {'n': nombre,'ap': ap_pat,'am': ap_mat,'u': usuario,'p': hashed,'d': departamento,'nivel': int(nivel),'c': correo})
        except Exception as e:
            flash(f'No se pudo guardar (tabla faltante o error): {e}','danger')
            return redirect(url_for('admin.accesos'))
        flash('Usuario creado','success')
        return redirect(url_for('admin.lista_usuarios'))
    return render_template('accesos.html')

@admin_bp.route('/usuarios')
@login_required
@nivel_acceso_required()
def lista_usuarios():
    q = text("SELECT [id],[Nombre],[Apellido Paterno],[Apellido Materno],[Usuario],[Password],[Departamento],[Nivel Acceso],[Correo] FROM CierreSucursales_Control_Accesos_Web")
    usuarios = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(q).fetchall()
        for r in rows:
            usuarios.append({'id':r[0],'Nombre':r[1],'Apellido_Paterno':r[2],'Apellido_Materno':r[3],'Usuario':r[4],'Password':r[5],'Departamento':r[6],'Nivel_Acceso':r[7],'Correo':r[8]})
    except Exception:
        flash('Tabla de usuarios no disponible en este entorno (test).','warning')
    return render_template('usuarios.html', usuarios=usuarios)

@admin_bp.route('/actualizar_usuario', methods=['POST'])
@login_required
@nivel_acceso_required()
def actualizar_usuario():
    data = request.form
    hashed = generate_password_hash(data.get('password')) if data.get('password') else None
    params = {'n': data.get('nombre'),'ap': data.get('apellido_paterno'),'am': data.get('apellido_materno'),'p': hashed,'d': data.get('departamento'),'nivel': int(data.get('nivel_acceso')),'id': int(data.get('id'))}
    try:
        with db.engine.begin() as conn:
            conn.execute(text("""UPDATE CierreSucursales_Control_Accesos_Web SET [Nombre]=:n,[Apellido Paterno]=:ap,[Apellido Materno]=:am,[Password]=:p,[Departamento]=:d,[Nivel Acceso]=:nivel WHERE id=:id"""), params)
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/eliminar_usuario', methods=['POST'])
@login_required
@nivel_acceso_required()
def eliminar_usuario():
    id_ = request.form.get('id')
    try:
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM CierreSucursales_Control_Accesos_Web WHERE id=:i"), {'i': int(id_)})
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/lista_Seguridad_Gerencias')
@login_required
@nivel_acceso_required()
def lista_Seguridad_Gerencias():
    q = text("""SELECT [ID],[Seguridad1],[Seguridad2],[Seguridad3],[Gerente1],[Gerente2],[Gerente3] FROM CierreSucursales_Gerentes ORDER BY [ID] DESC""")
    data = []
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(q).fetchall()
        data=[{'id':r[0],'Seguridad1':r[1],'Seguridad2':r[2],'Seguridad3':r[3],'Gerente1':r[4],'Gerente2':r[5],'Gerente3':r[6]} for r in rows]
    except Exception:
        flash('Tabla Seguridad/Gerencias no disponible en este entorno (test).','warning')
    return render_template('lista_Seguridad_Gerencias.html', Seguridad_Gerencias=data)

@admin_bp.route('/actualizar_Seguridad_Gerencia', methods=['POST'])
@login_required
@nivel_acceso_required()
def actualizar_Seguridad_Gerencia():
    f = request.form
    try:
        with db.engine.begin() as conn:
            conn.execute(text("""UPDATE CierreSucursales_Gerentes SET [Seguridad1]=:s1,[Seguridad2]=:s2,[Seguridad3]=:s3,[Gerente1]=:g1,[Gerente2]=:g2,[Gerente3]=:g3 WHERE [ID]=:id"""),
                         {'s1': f.get('Seguridad1'),'s2': f.get('Seguridad2'),'s3': f.get('Seguridad3'),'g1': f.get('Gerente1'),'g2': f.get('Gerente2'),'g3': f.get('Gerente3'),'id': f.get('id')})
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
