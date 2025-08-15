from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_babel import Babel
from celery import Celery
from prometheus_flask_exporter import PrometheusMetrics


db = SQLAlchemy()
mail = Mail()
babel = Babel()
celery = Celery(__name__)
# Configure Prometheus metrics without binding to an app yet. This allows the
# metrics exporter to be initialized later inside the application factory via
# ``metrics.init_app(app)`` without requiring an app object at import time.
# See https://github.com/rycus86/prometheus_flask_exporter for details.
metrics = PrometheusMetrics.for_app_factory()


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
