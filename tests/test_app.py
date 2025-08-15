import pytest
from cierre_farmacias_app import create_app

class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    LANGUAGES = ["es"]
    BABEL_DEFAULT_LOCALE = "es"
    LOG_LEVEL = "DEBUG"
    SENTRY_DSN = None


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr("cierre_farmacias_app.__init__.get_config", lambda: TestConfig)
    app = create_app()
    app.config.update(TESTING=True)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_app_creation(app):
    assert app.config["SECRET_KEY"] == "test"


def test_root_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")
