# Documentación de la API

El archivo [openapi.yaml](openapi.yaml) contiene la especificación OpenAPI de los endpoints disponibles.

## Visualización

Puedes visualizar la documentación utilizando [Swagger UI](https://swagger.io/tools/swagger-ui/) o [Redoc](https://redocly.com/):

```bash
npm install -g redoc-cli
redoc-cli bundle docs/api/openapi.yaml
```

Esto generará un archivo `redoc-static.html` con la documentación.

