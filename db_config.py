import os
from sqlalchemy import create_engine

DB_SERVER = os.getenv('DB_SERVER', 'MPWPAS01')
DB_NAME = os.getenv('DB_NAME', 'DBBI')
DB_USER = os.getenv('DB_USER', 'AlertDBBI')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'P4$9')
DB_TABLE = os.getenv('DB_TABLE', 'CierreSucursales4')

def get_connection_url():
    """Build the SQLAlchemy connection URL from environment variables."""
    return (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?"
        "driver=ODBC+Driver+17+for+SQL+Server"
    )

def get_engine(echo: bool = False):
    """Create a SQLAlchemy engine using the configured connection URL."""
    return create_engine(get_connection_url(), echo=echo)
