from sqlalchemy import create_engine
from config import get_config

cfg = get_config()
DB_TABLE = cfg.DB_TABLE


def get_connection_url():
    """Build the SQLAlchemy connection URL from configuration."""
    return cfg.SQLALCHEMY_DATABASE_URI


def get_engine(echo: bool = False):
    """Create a SQLAlchemy engine using the configured connection URL."""
    return create_engine(get_connection_url(), echo=echo)
