# Corrección de Storage y pegado de URLs

Base: foro_comunidades_multimedia.zip. Aplicar sobre esa versión, sin nuevas migraciones ni dependencias. No se ha modificado Supabase ni Vercel.

## Hallazgos
- El panel puede representar KB/MB en base 1024; la comprobación anterior rechazaba límites físicos superiores a los decimales. Ahora admite hasta 512000, 1048576, 2097152 y 10485760 bytes respectivamente. Los límites de archivo de la aplicación siguen siendo 500000, 1000000, 2000000 y 10000000. La cuota cuenta el máximo físico posible, incluso para reservas anteriores y canceladas hasta su eliminación. No cambia las restricciones SQL.
- Las claves sb_secret_ se enviaban como Bearer, a pesar de que las nuevas claves deben enviarse únicamente en apikey. Ahora se admiten ambas modalidades conservando SUPABASE_SERVICE_ROLE_KEY. No usar sb_publishable_.
- Se añaden mensajes específicos por bucket ausente, público, límite, MIME, fallo de autorización o conexión. No se exponen cuerpos de error, URLs firmadas ni claves.
- Se añade componente reutilizable para pegar URL por Ctrl+V o botón Pegar URL, con alternativa manual si el navegador deniega acceso al portapapeles. Se mueve el diálogo de creación al body mediante Teleport. No se pudo reproducir el problema de pegado en el navegador del usuario; la causa exacta permanece sin confirmar. Si se elige un archivo, tiene prioridad sobre la URL: quitar el archivo seleccionado antes de usar solo un enlace.

## Configuración de buckets (todos privados)
- foro-imagenes: 2 MB; image/jpeg, image/png, image/webp.
- foro-videos: 10 MB; video/mp4.
- foro-iconos: 500 KB; image/jpeg, image/png, image/webp.
- foro-portadas: 1 MB; image/jpeg, image/png, image/webp.

Consulta de solo lectura, opcional, en SQL Editor:
```sql
SELECT id, public, file_size_limit, allowed_mime_types
FROM storage.buckets
WHERE id IN ('foro-imagenes','foro-videos','foro-iconos','foro-portadas')
ORDER BY id;
```
No actualizar storage.buckets por SQL.

## Actualización local
Detener servicios, copiar archivos del ZIP conservando estructura, reiniciar los tres microservicios y Vite. Las variables SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY se requieren solo en el foro (5001), junto con DATABASE_URL y JWT_SECRET. No mostrar las credenciales. Si la clave es sb_secret_ puede conservarse en la misma variable. Ejecutar npm run build y el diagnóstico habitual; este último no prueba cargas reales.

## Pruebas
Python: 175 pruebas descubiertas, 150 superadas, 25 omitidas por dependencias ausentes. 10 nuevas pruebas aisladas sobre cabeceras, configuración, límites, cuotas y errores (incluyendo 2 casos de reserva binaria). JavaScript: 17/17. Sintaxis de tres scripts Vue modificados verificada con Node. No se ejecutó compilación Vue ni integración real de Storage por falta de dependencias y credenciales de prueba. No se confirma todavía la resolución del 503 específico del usuario, ni el pegado en su navegador. Probar icono, portada, imagen y video. No desplegar antes de comprobar.

Referencia: https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys
