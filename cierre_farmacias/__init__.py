from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config.settings import get_config
from pathlib import Path

db = SQLAlchemy()

def create_app(config_name='default'):
    # Root of repo (one level up from this package)
    base_dir = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(base_dir / 'templates'),
        static_folder=str(base_dir / 'static')
    )
    cfg = get_config(config_name)
    app.config.from_object(cfg)

    db.init_app(app)

    # Blueprints
    from .blueprints.core import core_bp
    from .blueprints.auth.routes import auth_bp
    from .blueprints.uploads.routes import uploads_bp
    from .blueprints.firmas.routes import firmas_bp
    from .blueprints.dashboard.routes import dashboard_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.pdfgen.routes import pdf_bp
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(firmas_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pdf_bp)
    # Deshabilita cache de HTML en modo DEBUG/Test para evitar plantillas obsoletas
    if app.config.get('DEBUG', False):
        @app.after_request
        def add_no_cache_headers(resp):
            ctype = resp.headers.get('Content-Type', '')
            if 'text/html' in ctype:
                resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                resp.headers['Pragma'] = 'no-cache'
                resp.headers['Expires'] = '0'
            return resp

    return app
