param(
    [string]$Port = "5020",
    [string]$Host = "10.30.45.88"
)

Write-Host "== Iniciando aplicación (host=$Host port=$Port) ==" -ForegroundColor Cyan

# Crear venv si no existe
if (-not (Test-Path -Path "$PSScriptRoot\Scripts\python.exe")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    py -3.11 -m venv . || (Write-Host "Error creando venv" -ForegroundColor Red; exit 1)
}

# Activar
.& "$PSScriptRoot\Scripts\Activate.ps1"

# Actualizar pip (solo si versión vieja)
$pipVersion = (pip --version) 2>$null
Write-Host "pip: $pipVersion"

# Verificación simple de imports clave (sin heredoc)
python -c "import flask, numpy, pandas" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Reinstalando dependencias (falló import flask/numpy/pandas)..." -ForegroundColor Yellow
    # Limpiar restos potenciales corruptos de numpy
    Get-ChildItem "$PSScriptRoot/Lib/site-packages/" -Filter numpy* -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    Get-ChildItem "$PSScriptRoot/Lib/site-packages/" -Filter numpy-*.whl -ErrorAction SilentlyContinue | ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
    pip install --no-cache-dir --force-reinstall -r requirements.txt || (Write-Host "Fallo instalación" -ForegroundColor Red; exit 1)
}

# Ejecutar la app
$env:FLASK_ENV="production"
# Para activar debug de forma temporal:  $env:FLASK_DEBUG="1"
$env:APP_HOST=$Host
$env:APP_PORT=$Port
$script = "app.py"
if (-not (Test-Path $script)) { Write-Host "No se encuentra $script" -ForegroundColor Red; exit 1 }

python $script
