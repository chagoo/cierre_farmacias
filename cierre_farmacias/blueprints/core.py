from flask import Blueprint, redirect, url_for, current_app, jsonify

core_bp = Blueprint('core', __name__)

@core_bp.route('/health')
def health_check():
    return {'status': 'ok'}

@core_bp.route('/')
def root():
    return redirect(url_for('auth.login'))

@core_bp.route('/_tmpl_debug')
def tmpl_debug():
    loader = getattr(current_app, 'jinja_loader', None)
    paths = []
    if loader and hasattr(loader, 'searchpath'):
        paths = list(loader.searchpath)
    return jsonify({'template_searchpath': paths, 'template_folder': current_app.template_folder})

# Ruta legacy: redirige "/aplicacion" a la vista actual de Órdenes
@core_bp.route('/aplicacion')
def aplicacion_legacy_redirect():
    return redirect(url_for('dashboard.ordenes'))
