Write-Host 'Python executable:' (Get-Command python).Source
Write-Host 'Pip location:' (Get-Command pip).Source
Write-Host 'Sys.path:'
python - <<'PY'
import sys,site,importlib,os
print('\n'.join(sys.path))
print('base prefix:', sys.base_prefix)
print('prefix:', sys.prefix)
print('executable:', sys.executable)
print('site-packages:', site.getsitepackages())
try:
    import numpy
    print('NUMPY OK ->', numpy.__version__)
except Exception as e:
    print('NUMPY FAIL ->', e)
PY

Write-Host 'Forzando reinstalacion numpy + pandas'
pip install --no-cache-dir --force-reinstall numpy==1.26.4 pandas==2.2.2
python - <<'PY'
try:
    import numpy, pandas
    print('POST INSTALL => numpy', numpy.__version__, 'pandas', pandas.__version__)
except Exception as e:
    print('POST INSTALL FAIL', e)
PY
