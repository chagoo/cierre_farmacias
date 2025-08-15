from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_babel import Babel
from celery import Celery


db = SQLAlchemy()
mail = Mail()
babel = Babel()
celery = Celery(__name__)


def init_celery(app):
    """Configure Celery with application context."""
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
    )

    class AppContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = AppContextTask
    return celery
