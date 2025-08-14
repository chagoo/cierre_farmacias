# Cierre Farmacias

Aplicación Flask modular para gestión de cierres de farmacias (carga de activos, flujo de firmas, administración de usuarios y generación de PDF).

## Estructura
```
cierre_farmacias/
  __init__.py              # App factory
  config/settings.py       # Configuración y selección de entorno
  blueprints/
    core.py                # /health
    auth/routes.py         # Login / logout
    uploads/routes.py      # Carga de Excel activos
    dashboard/routes.py    # Vistas de órdenes, activos, subdetalles
    firmas/routes.py       # Flujo de firmas y adjuntos
    admin/routes.py        # Gestión de usuarios y listas seguridad/gerencias
    pdfgen/routes.py       # Generación de PDFs usando scripts existentes
  utils/
    decorators.py          # Decoradores de autenticación
    email_utils.py         # Envío de correo SMTP
    notifications.py       # Notificaciones del flujo de firmas
    query_helpers.py       # Consultas reutilizables
    signatures.py          # Lógica de actualización de firmas
run.py                      # Punto de entrada
tests/                      # Pruebas Pytest
templates/                  # Plantillas activas
static/                     # Recursos estáticos
```

## Limpieza Realizada (2025-08-13)
Se eliminaron:
- Monolito legacy: UploadExcel_Monse3G*.py
- Plantillas obsoletas no referenciadas: activos_4/5, dashboard2_old_*, Index_3, Index_Whats, presentacion, subdetalles_4

Motivo: ya migradas a blueprints modulares y no usadas por rutas actuales ni pruebas.

## Próximos Pasos Recomendados
- Externalizar credenciales (usar .env y nunca commitear passwords reales) [Agregado: SMTP y rutas de uploads/templates]
- Añadir pruebas para: flujo completo de firmas con notificación (mock email), generación PDF (mock), carga Excel (casos de error)
- Añadir validación de tamaños y tipos en uploads de adjuntos [Implementado]
- Implementar limit rate / logging estructurado
- Dockerfile + CI (pytest)

## Ejecución (desarrollo)
1. Crear entorno virtual
2. Instalar dependencias
3. Exportar variables de entorno si aplica (.env)
4. Ejecutar `python run.py` (usa config 'dev')

## Testing rápido
`pytest -q`

## Seguridad
Reemplazar contraseñas hardcodeadas por variables de entorno. Considerar rotación y secrets manager.

## Generación PDF
Endpoint POST /PDF/<departamento>/<ceco> genera múltiples PDFs en carpeta BASE_UPLOAD\<dep>\<ceco>.
Los scripts de generación se empaquetaron en `cierre_farmacias/pdf_scripts/` y se cargan dinámicamente.
Config relevantes en `.env`:
- BASE_UPLOAD (por defecto P:\\UPLOAD)
- PDF_TEMPLATES_DIR (por defecto P:\\CierreFarmacias\\Plantillas)
- SMTP_SERVER/SMTP_PORT/SMTP_SENDER

## Configuración (.env)
Copiar `.env.example` a `.env` y ajustar:
- APP_SECRET_KEY: Secret Flask
- DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD: SQL Server (prod)
- UPLOAD_FOLDER: carpeta para Excel de carga
- BASE_UPLOAD: raíz para adjuntos de firmas (prod: P:\UPLOAD)
- EXCEL_ALLOWED_EXTS: extensiones permitidas para Excel
- ADJUNTOS_ALLOWED_EXTS: extensiones permitidas para adjuntos
- MAX_ADJUNTO_SIZE_MB: límite de tamaño por archivo
- SMTP_SERVER, SMTP_PORT, SMTP_SENDER: configuración de correo
- TEST_DB=sqlite: forzar SQLite en pruebas
- TEST_BASE_UPLOAD: carpeta temporal de adjuntos en pruebas
- TEST_MAX_ADJUNTO_SIZE_MB: límite en pruebas

Notas:
- En modo pruebas (config 'test' o TEST_DB=sqlite) no se consulta SQL Server en login; se permite sesión local.
- Asegura que la carpeta definida en BASE_UPLOAD exista y sea escribible por la app.
