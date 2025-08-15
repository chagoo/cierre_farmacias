# Cierre de Farmacias

Aplicación web para gestionar procesos de cierre de farmacias. Incluye autenticación, carga de archivos, generación de reportes y envío de notificaciones.

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
