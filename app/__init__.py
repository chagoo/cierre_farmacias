import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy instancia global
db = SQLAlchemy()

# Paths base for templates and static resources
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def build_db_uri() -> str:
    """Construye la URL de conexión a la base de datos desde variables de entorno."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    server = os.getenv("DB_SERVER", "")
    name = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    pwd = os.getenv("DB_PASSWORD", "")
    if all([server, name, user, pwd]):
        return (
            f"mssql+pyodbc://{user}:{pwd}@{server}/{name}?"
            "driver=ODBC+Driver+17+for+SQL+Server"
        )
    raise RuntimeError(
        "Faltan variables de entorno DB_SERVER, DB_NAME, DB_USER o DB_PASSWORD"
    )


def create_app():
    """Application factory para iniciar Flask y registrar blueprints."""
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=os.getenv("APP_SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=build_db_uri(),
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

