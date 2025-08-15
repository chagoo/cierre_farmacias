from flask import Flask, request
from .extensions import db, mail, babel, init_celery
from config import get_config

# Import blueprints
from .auth.routes import bp as auth_bp
from .uploads.routes import bp as uploads_bp
from .reports.routes import bp as reports_bp
from .notifications.routes import bp as notifications_bp

def create_app():
    """Application factory for cierre_farmacias."""
    app = Flask(__name__)
    config = get_config()
    app.config.from_object(config)

    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    init_celery(app)

    @babel.localeselector
    def get_locale():
        return request.accept_languages.best_match(app.config.get('LANGUAGES'))

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)

    return app
