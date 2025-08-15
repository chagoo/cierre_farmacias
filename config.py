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
    SECRET_KEY: str = os.environ.get("APP_SECRET_KEY", "change_me")
    SQLALCHEMY_DATABASE_URI: str = (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?"
        "driver=ODBC+Driver+17+for+SQL+Server"
    )

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
