# Guía de instalación y despliegue

## Prerrequisitos

- Python 3.11+
- [Redis](https://redis.io/) para tareas de Celery
- Base de datos SQL Server accesible

## Instalación

1. Clonar el repositorio:
   ```bash
   git clone <repo>
   cd cierre_farmacias
   ```
2. Crear y activar un entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Instalar dependencias:
   ```bash
   pip install -e .
   ```
4. Configurar variables de entorno en un archivo `.env` (ver `.env.example`):

| Variable | Descripción |
| --- | --- |
| `DB_SERVER` | Host del servidor SQL Server |
| `DB_NAME` | Nombre de la base de datos |
| `DB_USER` | Usuario de la base de datos |
| `DB_PASSWORD` | Contraseña del usuario |
| `APP_SECRET_KEY` | Clave secreta de Flask |
| `MAIL_SERVER` | Servidor SMTP |
| `MAIL_PORT` | Puerto SMTP |
| `MAIL_USERNAME` | Usuario SMTP |
| `MAIL_PASSWORD` | Contraseña SMTP |
| `CELERY_BROKER_URL` | URL de Redis para Celery |
| `CELERY_RESULT_BACKEND` | Backend de resultados de Celery |

5. Inicializar la base de datos si es necesario usando Alembic:
   ```bash
   alembic upgrade head
   ```

## Ejecución local

```bash
python run.py
```
La aplicación se iniciará en `http://localhost:5000`.

## Despliegue

1. Configurar variables de entorno en el servidor.
2. Instalar dependencias en modo producción: `pip install .`
3. Ejecutar migraciones de base de datos.
4. Lanzar la aplicación con un servidor WSGI, por ejemplo:
   ```bash
   gunicorn 'cierre_farmacias_app:create_app()'
   ```
5. Configurar un servicio supervisor o sistema similar para mantener el proceso.

