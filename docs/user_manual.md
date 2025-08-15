# Manual de usuario

## Inicio de sesión
1. Accede a `http://localhost:5000/login`.
2. Ingresa tu usuario y contraseña.
3. Si las credenciales son correctas serás redirigido al **dashboard**.

## Carga de archivos
1. Desde el dashboard selecciona la opción **Cargar archivo**.
2. Selecciona el archivo Excel y el **Tipo General** correspondiente.
3. Envía el formulario. El sistema procesará la información y enviará correos de notificación.

## Reportes
- `/data`: Devuelve la información procesada en formato JSON.
- `/summary`: Muestra un resumen de los datos.

## Notificaciones manuales
1. Envía una petición `POST` a `/send_notifications` con un cuerpo JSON:
   ```json
   {
     "ceco": "12345",
     "departamento": "Ventas"
   }
   ```
2. El sistema devolverá el resultado del envío de correos.

## Cierre de sesión
- Utiliza el enlace **Logout** para cerrar la sesión de forma segura.
