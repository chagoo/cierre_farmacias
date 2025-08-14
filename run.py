import os
from cierre_farmacias import create_app

config_name = os.getenv('APP_CONFIG', 'dev')
app = create_app(config_name)

# Allow env overrides for host/port
app.config['HOST'] = os.getenv('HOST', app.config.get('HOST','0.0.0.0'))
try:
    app.config['PORT'] = int(os.getenv('PORT', app.config.get('PORT', 5020)))
except ValueError:
    app.config['PORT'] = app.config.get('PORT', 5020)

if __name__ == '__main__':
    app.run(host=app.config.get('HOST','0.0.0.0'), port=app.config.get('PORT',5020))
