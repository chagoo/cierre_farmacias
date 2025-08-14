from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, send_from_directory, current_app
from sqlalchemy import text
from cierre_farmacias import db
from cierre_farmacias.utils.decorators import login_required
from cierre_farmacias.utils.signatures import load_signature_state, update_signatures
from cierre_farmacias.utils.notifications import send_flow_notification
import os
from werkzeug.utils import secure_filename

firmas_bp = Blueprint('firmas', __name__)

@firmas_bp.route('/adjuntos/<departamento>/<ceco>')
@login_required
def adjuntos(departamento, ceco):
    current_email = session.get('email','').lower().strip()
    state = load_signature_state(ceco, departamento)
    archivos = []
    base_upload = current_app.config.get('BASE_UPLOAD', r'P:\UPLOAD')
    folder_path = os.path.join(base_upload, departamento, ceco)
    if os.path.isdir(folder_path):
        for fn in os.listdir(folder_path):
            full = os.path.join(folder_path, fn)
            if os.path.isfile(full):
                archivos.append(fn)
    can = state.can_sign(current_email) if state else {r: False for r in ['solicitante','departamento','seguridad','gerente']}
    return render_template(
        'Adjuntos_4.html',
        archivos=archivos,
        departamento=departamento,
        ceco=ceco,
        can_sign_as_solicitante=can['solicitante'],
        can_sign_as_departamento=can['departamento'],
        can_sign_as_seguridad=can['seguridad'],
        can_sign_as_gerente=can['gerente'],
        firma_solicitante=state.firma_solicitante if state else None,
        firma_departamento=state.firma_departamento if state else None,
        firma_seguridad=state.firma_seguridad if state else None,
        firma_gerente=state.firma_gerente if state else None,
        correo1=getattr(state,'correo1',''),
        correo2=getattr(state,'correo2',''),
        correo3=getattr(state,'correo3',''),
        correo4=getattr(state,'correo4',''),
        correo5=getattr(state,'correo5',''),
        seguridad1=getattr(state,'seg1',''),
        seguridad2=getattr(state,'seg2',''),
        seguridad3=getattr(state,'seg3',''),
        gerente1=getattr(state,'ger1',''),
        gerente2=getattr(state,'ger2',''),
        gerente3=getattr(state,'ger3',''),
        DetallesFirmaSolicitante=getattr(state,'det_solicitante',''),
        DetallesFirmaDepartamento=getattr(state,'det_departamento',''),
        DetallesfirmaSeguridad=getattr(state,'det_seguridad',''),
        DetallesfirmaGerente=getattr(state,'det_gerente',''),
        user_full_name=session.get('nombre_completo','')
    )

@firmas_bp.route('/firmas/guardar/<departamento>/<ceco>', methods=['POST'])
@login_required
def guardar_firmas(departamento, ceco):
    res = update_signatures(ceco, departamento, session.get('email',''), request.form)
    code = 200 if res.get('updated') or res.get('message') else 400
    return jsonify(res), code

@firmas_bp.route('/firmas/notify/<departamento>/<ceco>/<stage>', methods=['POST'])
@login_required
def notify_flow(departamento, ceco, stage):
    result = send_flow_notification(ceco, departamento, stage)
    code = 200 if 'error' not in result else 400
    return jsonify(result), code

@firmas_bp.route('/adjuntos/subir/<departamento>/<ceco>', methods=['POST'])
@login_required
def subir_archivo(departamento, ceco):
    if 'archivo' not in request.files:
        return jsonify({'error':'Sin archivo'}),400
    f = request.files['archivo']
    if f.filename=='':
        return jsonify({'error':'Nombre vacío'}),400
    # Validación de tipo y tamaño
    allowed = {e.lower() for e in current_app.config.get('ADJUNTOS_ALLOWED_EXTS', set())}
    max_mb = float(current_app.config.get('MAX_ADJUNTO_SIZE_MB', 10))
    ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
    if allowed and ext not in allowed:
        return jsonify({'error': f'Extensión no permitida: .{ext}'}),400
    f.stream.seek(0, os.SEEK_END)
    size_bytes = f.stream.tell()
    f.stream.seek(0)
    if size_bytes > max_mb * 1024 * 1024:
        return jsonify({'error': f'Tamaño excede {max_mb} MB'}),400
    # Ruta segura
    base_upload = current_app.config.get('BASE_UPLOAD', r'P:\\UPLOAD')
    folder_path = os.path.join(base_upload, departamento, ceco)
    os.makedirs(folder_path, exist_ok=True)
    safe_name = secure_filename(f.filename)
    f.save(os.path.join(folder_path, safe_name))
    return redirect(url_for('firmas.adjuntos', departamento=departamento, ceco=ceco))

@firmas_bp.route('/adjuntos/eliminar/<departamento>/<ceco>', methods=['POST'])
@login_required
def eliminar_archivos(departamento, ceco):
    data = request.get_json(silent=True) or {}
    files = data.get('files', [])
    base_upload = current_app.config.get('BASE_UPLOAD', r'P:\UPLOAD')
    folder_path = os.path.join(base_upload, departamento, ceco)
    deleted = []
    for name in files:
        full = os.path.join(folder_path, name)
        if os.path.isfile(full) and os.path.commonpath([folder_path, full]) == folder_path:
            os.remove(full)
            deleted.append(name)
    return jsonify({'deleted': deleted})

@firmas_bp.route('/adjuntos/descargar/<departamento>/<ceco>/<filename>')
@login_required
def descargar_archivo(departamento, ceco, filename):
    base_upload = current_app.config.get('BASE_UPLOAD', r'P:\UPLOAD')
    folder_path = os.path.join(base_upload, departamento, ceco)
    if not os.path.isdir(folder_path):
        return jsonify({'error':'Directorio no existe'}),404
    return send_from_directory(folder_path, filename, as_attachment=True)
