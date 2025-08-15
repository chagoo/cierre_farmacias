# Guía de capacitación para nuevos integrantes

Bienvenido al proyecto **Cierre de Farmacias**. Esta guía te ayudará a comenzar rápidamente.

## 1. Configuración del entorno
- Sigue la [guía de instalación](installation_and_deployment.md) para preparar tu entorno.
- Crea un archivo `.env` con las variables necesarias.

## 2. Estructura del proyecto
- `cierre_farmacias_app/`: código principal de la aplicación.
- `templates/` y `static/`: recursos web.
- `tests/`: pruebas automatizadas.
- `docs/`: documentación.

## 3. Flujo de trabajo
1. Crea una rama a partir de `main` para tus cambios.
2. Instala dependencias de desarrollo:
   ```bash
   pip install -e .[dev]
   ```
3. Ejecuta las pruebas antes de hacer commit:
   ```bash
   pytest
   ```
4. Envía tus cambios mediante un Pull Request.

## 4. Estándares de código
- Sigue las convenciones de [PEP 8](https://peps.python.org/pep-0008/).
- Añade pruebas y documentación para nuevas funcionalidades.

## 5. Recursos adicionales
- [Documentación de Flask](https://flask.palletsprojects.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Celery](https://docs.celeryq.dev/)

¡Bienvenido al equipo!
