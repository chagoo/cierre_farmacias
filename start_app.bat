@echo off
REM Script minimo para iniciar la app evitando errores de sintaxis
set PORT=5020
set HOST=10.30.45.88
echo == Iniciando aplicacion (host=%HOST% port=%PORT%) ==

if not exist Scripts\python.exe (
  py -3.11 -m venv .
  if errorlevel 1 goto fail
)

call Scripts\activate.bat || goto fail

python -c "import flask" >nul 2>&1 || pip install -r requirements.txt || goto fail
python -c "import numpy, pandas" >nul 2>&1 || (
  for /d %%D in (Lib\site-packages\numpy*) do rd /s /q "%%D" 2>nul
  del /q Lib\site-packages\numpy-* 2>nul
  pip install --no-cache-dir --force-reinstall numpy==1.26.4 pandas==2.2.2 || goto fail
)

set APP_HOST=%HOST%
set APP_PORT=%PORT%
python app.py
goto end

:fail
echo Error al iniciar.
exit /b 1

:end
