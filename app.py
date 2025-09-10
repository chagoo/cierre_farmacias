"""Punto de entrada principal de la aplicación Flask.

Este archivo importa la app original (módulo con todas las rutas) desde
`UploadExcel_GR.py` (alias del original) y expone un entrypoint estándar (`python app.py`).

Para activar debug temporalmente:
  Windows PowerShell:  $env:FLASK_DEBUG="1"; python app.py
  CMD: set FLASK_DEBUG=1 && python app.py
"""
import os
from dotenv import load_dotenv

# Cargar variables desde .env si existe
load_dotenv()

from UploadExcel_GR import app  # noqa: F401


def main():
    host = os.getenv('APP_HOST', '0.0.0.0')
    try:
        port = int(os.getenv('APP_PORT', '5020'))
    except ValueError:
        port = 5020
    debug_env = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    # Reutilizamos la variable global app importada
    app.run(debug=debug_env, port=port, host=host, use_reloader=debug_env)


if __name__ == '__main__':
    main()
