from flask import Flask, request
import logging
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from .extensions import db, mail, babel, init_celery, metrics
from .utils.logging_setup import setup_logging
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

    setup_logging(app.config["LOG_LEVEL"])

    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    metrics.init_app(app)
    init_celery(app)

    @babel.localeselector
    def get_locale():
        return request.accept_languages.best_match(app.config.get('LANGUAGES'))

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)

    if app.config.get("SENTRY_DSN"):
        sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        sentry_sdk.init(
            dsn=app.config["SENTRY_DSN"],
            integrations=[FlaskIntegration(), sentry_logging],
            environment=app.config.get("ENV"),
        )

    return app
