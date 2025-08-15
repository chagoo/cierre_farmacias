# Cierre de Farmacias

Aplicación web para gestionar procesos de cierre de farmacias. Incluye autenticación, carga de archivos, generación de reportes
y envío de notificaciones.

## Contenido

- [Instalación y despliegue](docs/installation_and_deployment.md)
- [Documentación de API](docs/api/README.md)
- [Manual de usuario](docs/user_manual.md)
- [Guía de capacitación](docs/onboarding_guide.md)

## Requisitos

- Python 3.11+
- Acceso a una base de datos SQL Server
- Redis para tareas de Celery

## Uso rápido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # configurar variables
python run.py
```

Ejecute las pruebas con:

```bash
pytest
```

## Contenerización y despliegue

La aplicación incluye un `Dockerfile` y archivos de `docker-compose` para ambientes de **desarrollo** y **producción**.

```bash
# Ambiente de desarrollo
docker compose -f docker-compose.dev.yml up --build

# Ambiente de producción
docker compose -f docker-compose.prod.yml up --build -d
```

Scripts auxiliares:

- `scripts/deploy.sh [ambiente]` construye la imagen y despliega la aplicación.
- `scripts/rollback.sh [ambiente]` vuelve a la imagen previa registrada en `deploy_history.log`.
- `scripts/backup_db.sh` genera respaldos de la base de datos usando `sqlcmd`.
- `scripts/schedule_cron.sh` programa tareas de respaldo diario y rotación de logs.
- `scripts/logrotate.conf` configuración de rotación para `/var/log/cierre_farmacias/*.log`.

Estos scripts permiten automatizar el ciclo de vida de la aplicación y el mantenimiento periódico.
