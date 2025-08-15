import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration loaded from environment variables."""

    DB_SERVER: str = os.environ["DB_SERVER"]
    DB_NAME: str = os.environ["DB_NAME"]
    DB_USER: str = os.environ["DB_USER"]
    DB_PASSWORD: str = os.environ["DB_PASSWORD"]
    DB_TABLE: str = os.getenv("DB_TABLE", "CierreSucursales4")
    # SECRET_KEY must be provided via environment variable to avoid using
    # a hard-coded default. This value should be managed securely outside
    # the codebase (e.g. environment variable or secrets manager).
    SECRET_KEY: str = os.environ["APP_SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI: str = (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?"
        "driver=ODBC+Driver+17+for+SQL+Server"
    )

    # Email configuration
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "smtp.example.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS: bool = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL: bool = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME: str | None = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD: str | None = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER: str = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@example.com")

    # Celery configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # Localization
    LANGUAGES: list[str] = ["es", "en"]
    BABEL_DEFAULT_LOCALE: str = os.getenv("BABEL_DEFAULT_LOCALE", "es")

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

def get_config():
    """Return the configuration class based on the ENV variable."""
    env = os.environ.get("ENV", "development").lower()
    return CONFIG_MAP.get(env, Config)
