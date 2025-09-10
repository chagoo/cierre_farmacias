"""Punto de entrada principal de la aplicación Flask.

Este archivo ahora utiliza la factoría ``create_app`` del paquete ``app``
para inicializar la aplicación y ejecutar el servidor.

Para activar debug temporalmente:
  Windows PowerShell:  $env:FLASK_DEBUG="1"; python app.py
  CMD: set FLASK_DEBUG=1 && python app.py
"""
import os
from dotenv import load_dotenv

# Cargar variables desde .env si existe
load_dotenv()

from app import create_app


def main():
    host = os.getenv('APP_HOST', '0.0.0.0')
    try:
        port = int(os.getenv('APP_PORT', '5020'))
    except ValueError:
        port = 5020
    debug_env = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')

    app = create_app()
    app.run(debug=debug_env, port=port, host=host, use_reloader=debug_env)


if __name__ == '__main__':
    main()
