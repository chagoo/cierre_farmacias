# Aplicación Cierre de Sucursales

## Resumen
Aplicación Flask para gestionar proceso de cierre de sucursales (activos, órdenes, adjuntos, generación de PDFs y notificaciones por correo). El archivo principal ahora se referencia como `UploadExcel_GR.py`. El punto de entrada estándar es `app.py`.

## Estructura Clave
- `app.py`: Punto de entrada (arranca el servidor Flask). 
- `UploadExcel_GR.py`: Contiene rutas, modelos y lógica principal.
- `templates/`: Vistas HTML (login, dashboard, etc.).
- `static/`: Recursos estáticos (css, js, imágenes, presentaciones).
- `Plantillas/`: Archivos Excel / plantillas para procesos.
- `start_app.ps1` / `start_app.bat`: Scripts para iniciar rápidamente.
- `requirements.txt`: Dependencias de Python.

## Requisitos
- Windows + Python 3.11 instalado y accesible vía `py -3.11`
- Driver: ODBC Driver 17 for SQL Server.

## Instalación Rápida
```powershell
cd E:\apps\app_cierres
py -3.11 -m venv .
./Scripts/Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# (Opcional) Copiar .env.example a .env y editar credenciales:
# copy .env.example .env
```

## Ejecución
### PowerShell
```powershell
./start_app.ps1          # Producción (sin debug)
$env:FLASK_DEBUG="1"; ./start_app.ps1   # Con debug
```
### CMD
```
start_app.bat
set FLASK_DEBUG=1 && start_app.bat
```
### Manual
```powershell
python app.py
```

La app toma variables de entorno opcionales:
- `APP_HOST` (default `0.0.0.0`)
- `APP_PORT` (default `5020`)
- `FLASK_DEBUG` (1/true para activar modo debug)

Ejemplo:
```powershell
$env:APP_HOST="10.30.45.88"; $env:APP_PORT="5020"; python app.py
```

El archivo `app.py` carga automáticamente un `.env` si está presente (usando `python-dotenv`).

## Notas de Seguridad
Configurar credenciales y secretos en variables de entorno o archivo `.env` (no versionado):
```
DB_SERVER=MPWPAS01
DB_NAME=DBBI
DB_USER=AlertDBBI
DB_PASSWORD=xxxxxxx
APP_SECRET_KEY=una_clave_secreta_segura
```
Luego en código:
```python
import os
DB_SERVER = os.getenv('DB_SERVER')
```

## Problemas Comunes
1. `ImportError: No module named 'numpy'`: Reinstalar numpy/pandas con `pip install --no-cache-dir --force-reinstall numpy pandas`.
2. `The requested address is not valid in its context`: La IP configurada no pertenece a la máquina; usar una IP local válida o `0.0.0.0`.
3. Lentitud en `/data`: Crear índice en SQL Server:
```sql
CREATE NONCLUSTERED INDEX IX_CierreSucursales4_Dep_Accion
ON dbo.CierreSucursales4 (Departamento, Accion);
```

## Migración de contraseñas (SHA2_256/Plano -> Hash seguro)

Se agregó un script para migrar los passwords existentes a hashes seguros de Werkzeug. Soporta:
- Dejar intactos los que ya están hasheados (scrypt/pbkdf2).
- Detectar SHA2_256 en HEX (64 caracteres, con/sin 0x) y reasignar un password temporal.
- Detectar texto plano y hashearlo manteniendo la misma contraseña.

Pasos (PowerShell en Windows):

1. Opcional: define una contraseña temporal fija que quieras usar para todos los reseteos (de lo contrario se generará aleatoria por usuario):

```powershell
$env:DEFAULT_TEMP_PASSWORD = "Temporal#2025"
```

2. DRY RUN (no cambios, solo reporte CSV):

```powershell
.\Scripts\python.exe .\maintenance\migrate_passwords.py --dry-run
```

3. Aplicar cambios:

```powershell
.\Scripts\python.exe .\maintenance\migrate_passwords.py --apply
```

4. Revisa el CSV generado en la carpeta del proyecto (migrated_passwords_YYYYMMDD_HHMMSS.csv) con el detalle de usuarios y contraseñas temporales cuando aplique.

Después de la migración, el login seguirá aceptando los tres formatos pero los usuarios migrados quedarán con hash seguro.
## Próximas Mejores Prácticas (Sugeridas)
- Extraer configuración a `config.py`.
- Añadir pruebas unitarias mínimas.
- Implementar `.env` + `python-dotenv`.
- Cambiar a un servidor WSGI (gunicorn / waitress) para producción.
- Añadir logging estructurado (JSON) para monitoreo.

## Tablas SQL utilizadas (documentación)
Base de datos: `DBBI` (schema `dbo`). La app lee y/o escribe en las siguientes tablas:

- dbo.CierreSucursales4
	- Propósito: Tabla principal del proceso de cierre (activos por CECO/Departamento, flujo de firmas, correos, estados, etc.).
	- Operaciones: lectura general, inserciones por carga de Excel, actualizaciones de acción (Baja/Traspaso), firmas, generación de listados y adjuntos, consultas de dashboard.
	- Columnas referenciadas (no exhaustivo, principales):
		- Identificación y organización: `ID`, `Departamento`, `Ceco`, `Ceco Destino`, `Tipo`, `Tipo_General`.
		- Activo: `Soc.`, `[Act. Fijo]`, `Clase`, `[Fe. Capit.]`, `[Denominacion del activo fijo]`, `[Val. Cont.]`, `Mon.`, `Orden`, `Operativo`, `Observaciones`, `Unidades`, `PrecioUnitario`, `Tipo de Activo`.
		- Estados generales: `FechaIni`, `FechaFin`, `Estatus`, `Estatus_General`, `Accion`.
		- Ubicación y responsables: `Farmacia`, `Domicilio`, `Ciudad`, `Estado`, `GerenteOP`, `Director`.
		- Contactos (notificaciones): `[Correo 1..5]`, `[Nivel Correo 1..5]`.
		- Firmas: `FirmaSolicitante`, `DetallesFirmaSolicitante`, `FirmaDepartamento`, `DetallesFirmaDepartamento`, `FirmaSeguridad`, `DetallesFirmaSeguridad`, `FirmaGerente`, `DetallesFirmaGerente`.

- dbo.CierreSucursales_Control_Accesos_Web
	- Propósito: Control de accesos de usuarios del sistema web.
	- Operaciones: autenticación (lectura), alta/edición/baja de usuarios (escritura), migración a hash de contraseña.
	- Columnas referenciadas: `id`, `Nombre`, `Apellido Paterno`, `Apellido Materno`, `Usuario`, `Password`, `Departamento`, `Nivel Acceso`, `Correo`.

- dbo.CierreSucursales_Gerentes
	- Propósito: Catálogo de destinatarios de Seguridad y Gerencia para el flujo de firmas y notificaciones.
	- Operaciones: lectura para notificaciones y permisos de firma; edición desde panel de administración.
	- Columnas referenciadas: `ID`, `Seguridad1`, `Seguridad2`, `Seguridad3`, `Gerente1`, `Gerente2`, `Gerente3`.

Sugerencias de índices (opcional):
- `CierreSucursales4(Departamento, Accion)` para endpoints de dashboard.
- `CierreSucursales4(Ceco, Departamento)` para vistas de detalles/subdetalles y adjuntos.

## Licencia
Uso interno.

## Mapa de navegación (rutas → vistas → acciones)

Esta guía resume cómo navega el usuario por la aplicación, qué plantilla HTML se renderiza en cada ruta y qué acciones dispara cada página.

### 1) Autenticación y utilidades de cuentas
- GET /login → plantilla: `templates/login.html`
	- POST /login: autentica; si es correcto, redirige a /dashboard.
- GET /logout → limpia sesión y redirige a /login.
- GET /signup → `templates/signup.html`
	- POST /signup: alta de usuario (controlado por token/tabla vacía); redirige a /login.
- GET|POST /bootstrap_admin → `templates/bootstrap_admin.html` (bootstrap del primer admin cuando no hay usuarios)
	- POST /bootstrap_admin_api: variante JSON para automatización.
- GET /migrar_passwords → `templates/migrar_passwords.html`
	- POST /migrar_passwords: ejecuta migración (dry-run o apply) y devuelve JSON/CSV.

### 2) Dashboard y navegación principal
- GET /dashboard → `templates/dashboard2.html`
	- Desde la barra de navegación (header) se accede a: Accesos (/accesos), Lista de Usuarios (/usuarios), App Cierre Farmacias (/aplicacion), Seguridad y Gerencia (/lista_Seguridad_Gerencias).

### 3) App Cierre Farmacias (flujo operativo)
- GET /aplicacion → `templates/Index_3.html` (entrada a la app de cierres)
- GET /ordenes → `templates/Ordenes.html`
- GET /subordenes → `templates/subordenes2.html`
	- POST /actualizar_subordenes: guarda cambios en subórdenes.
- GET|POST /detalles/<detalle_id> → `templates/detalles_2.html`
- GET|POST /subdetalles/<Departamento>/<Ceco> → `templates/subdetalles_5.html`
- GET|POST /activos/<activo_id> → `templates/activos_4.html`
- GET /activos → `templates/activos.html`
- Adjuntos por CECO/Departamento:
	- GET /adjuntos/<departamento>/<ceco> → `templates/Adjuntos_4.html`
	- POST /subir/<departamento>/<ceco> → carga de archivos
	- POST /eliminar_archivos/<departamento>/<ceco> → elimina archivos seleccionados
	- GET /descargar/<dep>/<ceco>/<filename> → descarga un archivo
- POST /PDF/<departamento>/<ceco> → genera PDFs llamando a scripts: `PDF7_Traspaso.py`, `PDF_BAJA.py`, `PDF_Tecnico.py`, `pdf_Recoleccion.py`.

### 4) Carga de Excel
- GET|POST /upload → `templates/index_excel_Monse5.html` (carga de archivos Excel)

### 5) Gestión de accesos y usuarios
- GET|POST /accesos → `templates/accesos.html` (alta rápida de usuario)
- GET /usuarios → `templates/Usuarios.html`
	- POST /actualizar_usuario → actualiza datos/contraseña
	- POST /eliminar_usuario → elimina el usuario

### 6) Seguridad y Gerencia
- GET /lista_Seguridad_Gerencias → `templates/lista_Seguridad_Gerencias.html`
	- POST /actualizar_Seguridad_Gerencia → actualiza destinatarios (Seguridad/Gerencia)

### 7) Datos, reportes y utilidades
- GET /data → devuelve JSON (dataset para gráficos/tableros)
- GET /summary → endpoint auxiliar (resumen)
- GET /presentacion → `templates/presentacion.html` (muestra deck de presentación)
- GET /check_files → verificación/health-check

### 8) Parciales y layout compartido
- `templates/partials/header.html` → Navbar reutilizable.
	- Variables de contexto: `header_brand` (texto del branding) y `active_page` (resalta la opción actual: 'inicio' | 'accesos' | 'usuarios', etc.).
	- Uso típico en una página:
		- `{% set active_page = 'usuarios' %}`
		- `{% set header_brand = 'Sistema de Gestión' %}`
		- `{% include 'partials/header.html' %}`
- `templates/partials/footer.html` → Pie reutilizable con año dinámico.
	- Variable: `current_year` (inyectada globalmente desde `UploadExcel_GR.py`).
	- Uso: `{% include 'partials/footer.html' %}`

### 9) Flujo típico del usuario
- Login → Dashboard → App Cierre Farmacias → Órdenes → Subórdenes → Detalles/Subdetalles → Adjuntos y/o Generación de PDF.
- Login → Accesos → alta de usuario → Usuarios (edición/baja).
- Login → Seguridad y Gerencia → edición de destinatarios.

Notas:
- Algunas rutas POST devuelven JSON para ser consumido vía AJAX desde las plantillas (por ejemplo: actualizar_subordenes, actualizar_usuario, actualizar_Seguridad_Gerencia, migrar_passwords).
- Autorización: varias páginas requieren sesión con `Nivel Acceso = 2`.
