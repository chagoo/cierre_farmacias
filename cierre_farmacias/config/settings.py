import os
from pathlib import Path

# Load .env if present (simple implementation to avoid extra dependency)
ENV_PATH = Path(__file__).resolve().parent.parent.parent / '.env'
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        if not line or line.strip().startswith('#') or '=' not in line:
            continue
        k,v = line.split('=',1)
        os.environ.setdefault(k.strip(), v.strip())

class Config:
    SECRET_KEY = os.getenv('APP_SECRET_KEY', 'change-me-in-.env')
    DB_SERVER = os.getenv('DB_SERVER', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'DBBI')
    DB_USER = os.getenv('DB_USER', 'sa')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    # Note: provide real creds via environment (.env). Defaults are placeholders.
    SQLALCHEMY_DATABASE_URI = (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Excel uploads (ingest)
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = {e.strip().lower() for e in os.getenv('EXCEL_ALLOWED_EXTS', 'xlsx,xls').split(',') if e.strip()}
    # Adjuntos (firmas) uploads validation
    BASE_UPLOAD = os.getenv('BASE_UPLOAD', r'P:\UPLOAD')
    # PDF templates base directory
    PDF_TEMPLATES_DIR = os.getenv('PDF_TEMPLATES_DIR', r'P:\CierreFarmacias\Plantillas')
    ADJUNTOS_ALLOWED_EXTS = {e.strip().lower() for e in os.getenv('ADJUNTOS_ALLOWED_EXTS', 'pdf,jpg,jpeg,png,doc,docx,xls,xlsx').split(',') if e.strip()}
    MAX_ADJUNTO_SIZE_MB = float(os.getenv('MAX_ADJUNTO_SIZE_MB', '10'))
    # SMTP / Email
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'localhost')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '25'))
    SMTP_SENDER = os.getenv('SMTP_SENDER', 'no-reply@example.com')

class DevConfig(Config):
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 5020

class TestConfig(Config):
    TESTING = True
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    # Allow overriding with an in-memory sqlite for faster tests
    if os.getenv('TEST_DB', 'sqlite').lower() == 'sqlite':
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Lighter defaults for tests
    BASE_UPLOAD = os.getenv('TEST_BASE_UPLOAD', str(Path.cwd() / 'test_uploads'))
    MAX_ADJUNTO_SIZE_MB = float(os.getenv('TEST_MAX_ADJUNTO_SIZE_MB', '1'))

config_map = {
    'default': Config,
    'dev': DevConfig,
    'test': TestConfig,
}

def get_config(name: str):
    return config_map.get(name, Config)()
