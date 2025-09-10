import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy instancia global

db = SQLAlchemy()


def create_app():
    """Application factory para iniciar Flask y registrar blueprints."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("APP_SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///:memory:"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)

    # Registro de blueprints
    from .auth import auth_bp
    from .uploads import uploads_bp
    from .pdf import pdf_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(admin_bp)

    return app
