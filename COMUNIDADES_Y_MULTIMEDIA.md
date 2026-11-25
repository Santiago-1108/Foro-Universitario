# Comunidades y multimedia — entrega para validación

Base: `foro_final_auditado.zip` (último ZIP entregado en la conversación). No se ha conectado al computador del propietario, a su Supabase ni a Vercel. Se conservaron las migraciones 001–009, las dependencias, la configuración de despliegue y la autenticación JWT existente. Esta entrega **no está validada para producción**.

## 1. Alcance y decisiones

### Comunidades
- Las categorías y los seguimientos anteriores se mantienen. `comunidades` tiene una categoría temática; `preguntas.id_comunidad` es opcional y una FK compuesta obliga a que su categoría coincida. Las preguntas antiguas conservan `NULL` en ese campo.
- Creación autenticada mediante modal nativo de cuatro pasos: temática, tipo, datos, personalización. Nombre insensible a mayúsculas y slug únicos; límites de texto; dueño y miembro aprobados en la misma transacción.
- Tipos **pública** (cualquier usuario autenticado puede publicar/comentar) y **restringida** (lectura pública, creación de preguntas/respuestas/comentarios solo para miembros aprobados). Los triggers de la BD aplican la restricción aun cuando las escrituras se realicen desde el servicio de interacciones; el endpoint de creación también comprueba permisos.
- Propietario puede editar descripción, nombre, normas, icono y portada, aprobar solicitudes, expulsar miembros y asignar/revocar moderadores. Propietario y moderador pueden fijar, cerrar, reabrir o retirar publicaciones de su propia comunidad. No se permite expulsar al dueño ni cambiar el tipo, la temática o el identificador. Expulsar no equivale a un veto permanente.
- Directorio de comunidades, página individual por slug, listado paginado, conteo real de miembros, normas, moderadores y acceso al feed interactivo existente. Se integra con el menú lateral, Explorar, Mis comunidades, búsqueda global, creación de preguntas y Para ti/Siguiendo. La lista de destinos del formulario muestra hasta 21 comunidades de la primera página y la comunidad seleccionada desde su página; para otras, entra directamente a su página y pulsa Crear publicación.
- **Comunidades privadas no habilitadas**: el servidor y la restricción SQL rechazan ese tipo. Las lecturas públicas heredadas del foro, perfiles, karma, votos, historial, notificaciones y administración necesitan una auditoría de autorización por comunidad antes de activar privacidad real. No se simula un tipo privado ni se expone contenido pretendidamente privado. Falta ampliar la moderación de comunidades a respuestas/comentarios y paginar la gestión de miembros. Las categorías siguen siendo un mecanismo de navegación global.

### Multimedia
- Se conservan los tipos texto, imagen por URL HTTPS, enlace y encuesta. Se añaden `multimedia` (1–3 imágenes) y `video` (1 MP4). Texto de acompañamiento opcional para ambos nuevos tipos. No se mezclan videos e imágenes en la misma publicación. El texto de las publicaciones antiguas sigue siendo obligatorio.
- Selección y arrastre, vistas previas, eliminación previa, progreso XHR, carrusel de imágenes, reproductor nativo sin autoplay y preload none, carga de enlaces de publicaciones diferida mediante IntersectionObserver. Se intenta comprimir imágenes que excedan el límite mediante canvas/WebP, con un máximo de entrada de 12 MB y resolución comprobada tras decodificar. No hay transcodificación de video.
- Iconos y portadas pueden cargarse o continuar como URL HTTPS. Se usa la misma autorización de carga. Las rutas de objetos, nunca los binarios ni enlaces firmados persistentes, se guardan en `archivos_foro`. Se puede retirar/reemplazar un icono o portada desde la administración de comunidad.
- Se conservan votos, guardados, respuestas, encuestas y notificaciones existentes. Los nuevos tipos se muestran en Inicio, detalle, resultados de búsqueda, perfil y comunidades. En las pestañas de actividad las vistas previas multimedia se muestran para las publicaciones, no para respuestas.
- El borrador conserva los datos textuales y el destino; no conserva archivos temporales del navegador. Los archivos adjuntos de una publicación ya creada no son editables; editar texto sigue disponible.

## 2. Infraestructura gratuita

Fuentes oficiales consultadas el 24/11/2026:
- https://supabase.com/pricing — Free: 1 GB de almacenamiento y 50 MB máximo por archivo.
- https://supabase.com/docs/guides/storage/serving/bandwidth — 5 GB de transferencia en caché y 5 GB sin caché por organización Free; son cuotas separadas, no una única bolsa intercambiable.
- https://supabase.com/docs/guides/storage/uploads/file-limits — límites globales y de bucket.
- https://supabase.com/docs/guides/storage/uploads/standard-uploads — PUT directo con autorización firmada, sin enviar binarios al backend.
- https://supabase.com/docs/guides/storage/uploads/resumable-uploads — TUS recomendado para archivos mayores de 6 MB. Esta versión utiliza carga estándar también para videos de hasta 10 MB; reanudar una transferencia interrumpida queda pendiente.
- https://vercel.com/docs/functions/limitations — límite habitual de payload de función 4,5 MB. No dependemos de aumentos en beta.
- https://vercel.com/docs/plans/hobby — uso personal no comercial. Confirmar elegibilidad si el proyecto pasa a ser institucional.

Se utilizan bytes decimales: 2 000 000 por imagen, 10 000 000 por video, 500 000 por icono, 1 000 000 por portada. 30 000 000 por usuario y 800 000 000 globales del foro. Las cuotas pueden ajustarse en las constantes de `routes/multimedia.py` y, para límites por tipo, conjuntamente con las restricciones de 011, los buckets y el cliente. **No subir los límites de un bucket por encima de los límites del código**.

La cuota reserva el máximo de cada bucket, incluso si el archivo declarado es menor: así no depende de un tamaño aportado por el navegador. `pg_advisory_xact_lock` serializa las reservas y se contabilizan cargas pendientes, canceladas, verificadas y adjuntas. Es una cuota conservadora, por lo que la capacidad real disponible puede ser inferior a 30 MB por usuario. No controla objetos creados manualmente fuera de la app, ni la transferencia mensual, ni recursos de otros proyectos. Revisa Storage y Usage con frecuencia. Un video de 10 MB reproducido 500 veces ya puede consumir aproximadamente 5 GB.

## 3. Seguridad y ciclo de vida de los archivos

1. Vue solicita una reserva autenticada a Flask, con MIME, tamaño y uso.
2. Se comprueba que el bucket exista, sea privado, tenga límite físico menor o igual al permitido y admita únicamente los MIME esperados. Se genera un UUID y una ruta propiedad del usuario.
3. La reserva se confirma en PostgreSQL antes de emitir una URL temporal de subida (sin upsert). Se construye usando solo la URL de proyecto configurada en el servidor. No se devuelve la clave de servicio.
4. El navegador realiza PUT directamente contra Storage. Vercel solo recibe JSON de autorización, verificación y publicación.
5. El backend consulta metadatos de `storage.objects` y comprueba los primeros 32 bytes del objeto mediante una lectura acotada. Se rechazan formatos/longitudes que no coincidan. Esta comprobación de cabeceras no es un antivirus, un decodificador completo ni una validación del códec del MP4; no garantiza que el archivo sea inocuo o reproducible. No se permiten SVG, HTML ni ejecutables como tipos declarados.
6. Al crear publicación/comunidad se bloquean las filas de reservas verificadas y se comprueba propiedad, bucket, estado y vencimiento antes de asociarlas. La misma reserva no se puede adjuntar a dos contenidos.
7. Los buckets privados se sirven mediante enlaces firmados de 5 minutos. El lector de publicación comprueba publicación no eliminada y bloqueos de la sesión. Las comunidades públicas y restringidas tienen lectura pública. Un enlace ya emitido puede seguir funcionando hasta caducar; no compartirlo como una URL permanente. La reproducción puede necesitar renovar el enlace después de su vencimiento.
8. Cancelar una reserva no libera la cuota inmediatamente: el enlace de subida de Supabase dura 2 horas. La reserva se conserva por 3 horas para evitar liberar capacidad mientras la autorización todavía pueda utilizarse. El botón «Liberar archivos huérfanos vencidos» limpia hasta tres archivos propios sin adjuntar o asociados a una publicación eliminada, después de ese intervalo. El objeto se borra por la API de Storage, no con DELETE de storage.objects. La cuota se libera solo al confirmar la ausencia del objeto. Si falla la subida, vuelve a seleccionar/reintentar según el mensaje; las reservas fallidas siguen contándose hasta su limpieza. No hay un job programado ni una limpieza global automática.

**Condición necesaria:** no crear políticas abiertas de SELECT, INSERT, UPDATE o DELETE en estos buckets. Revisar también políticas globales existentes de `storage.objects` que pudieran otorgar acceso. El flujo utiliza el service_role solo en Flask y enlaces firmados. No comparte el JWT propio con Storage. La configuración de Storage y las políticas reales del usuario no han sido verificadas.

## 4. Migraciones

Aplicar en una base de pruebas que ya tenga 001–009, en este orden:

1. `backend/database/migrations/010_comunidades.sql`
2. `backend/database/migrations/011_multimedia.sql`

010 crea `comunidades`, `miembros_comunidades`, `preguntas.id_comunidad`, índices, FK y triggers de participación. 011 crea `archivos_foro` y amplía la restricción `preguntas_tipo_valido` (reemplaza exclusivamente la restricción; no borra registros/columnas). Se mantienen RLS y los permisos restringidos de las nuevas tablas. Estas dos migraciones deben estar aplicadas **antes de iniciar la versión consolidada**. No ejecutar `setup.sql` sobre una base existente. No se han aplicado estas migraciones a ninguna base real. Antes de producción, probar con datos de prueba, hacer copia de seguridad y revisar compatibilidad con otros consumidores de la BD.

## 5. Configurar Supabase Storage desde el panel

En el mismo proyecto Supabase de **pruebas** al que apunta `DATABASE_URL`:

1. Abre Storage → Settings. Configura un límite global que admita los videos (al menos el límite del bucket de video, sin superar el plan Free). Si otros buckets ya existen, no cambies su funcionamiento sin revisarlo.
2. Storage → Buckets → New bucket. Crea **cuatro buckets privados** (Public bucket desactivado). Activa Restrict file size y Restrict MIME types. Usa estos nombres exactos:

| Bucket | Máximo (bytes) | MIME permitidos |
|---|---:|---|
| `foro-imagenes` | 2000000 | image/jpeg, image/png, image/webp |
| `foro-videos` | 10000000 | video/mp4 |
| `foro-iconos` | 500000 | image/jpeg, image/png, image/webp |
| `foro-portadas` | 1000000 | image/jpeg, image/png, image/webp |

3. Si el panel usa MiB/KiB, elige un valor igual o ligeramente inferior al límite en bytes. El backend rechaza buckets más permisivos. Puedes consultar la configuración (solo lectura) desde SQL Editor:

```sql
SELECT id, public, file_size_limit, allowed_mime_types
FROM storage.buckets
WHERE id IN ('foro-imagenes','foro-videos','foro-iconos','foro-portadas');
```

Si el panel no admite la precisión requerida, usa valores menores (p. ej., 1953 KiB, 9765 KiB, 488 KiB y 976 KiB respectivamente), o configura el tamaño en bytes desde la API de administración de Storage siguiendo https://supabase.com/docs/guides/storage/buckets/creating-buckets. No alteres `storage.objects` ni `storage.buckets` directamente con SQL de escritura.
4. En Storage → Policies verifica que no existan políticas globales o específicas que permitan acceso público/directo a estos buckets. No necesitas crear políticas de acceso para este flujo.
5. En Project Settings → API Keys, copia la clave privada legacy `service_role` y la URL del proyecto. Si no tienes habilitada esa clave, no actives cargas hasta adaptar y comprobar el método de autenticación de Storage a la clave disponible. No pegues secretos en el chat, en el README, en GitHub ni en las variables `VITE_...`.

## 6. Ejecutar en Windows

Descomprime la actualización en la raíz de `foro2.0` después de respaldar los cambios locales. Mantén `.venv`, `node_modules` y las variables existentes. Detén todos los procesos de la versión anterior. Aplica 010 y 011 en pruebas. En la terminal del microservicio de foro, además de `DATABASE_URL` y `JWT_SECRET`, configura:

```powershell
$env:SUPABASE_URL='https://TU_PROYECTO.supabase.co'
$env:SUPABASE_SERVICE_ROLE_KEY='TU_CLAVE_PRIVADA_SERVICE_ROLE'
```

No hacen falta claves `anon` ni variables nuevas en Vue. Si faltan las variables de Storage, los servicios pueden arrancar, pero las cargas devuelven un error 503. Configura la URI PostgreSQL y el JWT como ya lo hacías, usando la misma BD y clave JWT en los tres servicios.

Desde la raíz, en tres terminales independientes (variables configuradas):

```powershell
.\.venv\Scripts\python.exe backend/app_usuarios.py
.\.venv\Scripts\python.exe backend/app_preguntas.py
.\.venv\Scripts\python.exe backend/app_interacciones.py
```

En la cuarta terminal, desde la raíz:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

En la quinta terminal, desde la raíz:

```powershell
.\.venv\Scripts\python.exe backend/tests/verificar_servicios.py --puerto-frontend 5173
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p 'test_*.py' -v
cd frontend
node --test tests/api.test.mjs tests/actividad.test.mjs
npm run build
```

La revisión de la API cambió a `comunidades-multimedia-1`. Todos los servicios y Vue deben ejecutarse desde la misma carpeta actualizada. Si aparece un 400/404 por una ruta nueva, comprueba la revisión, los prefijos y las migraciones. No confundas un error de conexión de IPv4/IPv6 con una consulta fallida de la BD.

## 7. Endpoints

Prefijo `/api/foro` (rutas internas Flask):

| Método | Ruta | Autorización |
|---|---|---|
| GET | /comunidades?q=&mias=1&offset= | Pública; mias exige sesión |
| POST | /comunidades | JWT |
| GET | /comunidades/:slug | Pública |
| PUT | /comunidades/:id | Propietario |
| PUT | /comunidades/:id/membresia | JWT |
| GET | /comunidades/:id/miembros | Propietario |
| PUT | /comunidades/:id/miembros/:uid | Propietario |
| PUT | /comunidades/:id/preguntas/:pid | Propietario/moderador de esa comunidad |
| POST | /multimedia/reservar | JWT |
| PUT | /multimedia/:uuid/verificar | Propietario de reserva |
| DELETE | /multimedia/:uuid | Propietario de reserva |
| POST | /multimedia/limpiar | JWT, archivos propios |
| GET | /multimedia/publicaciones/:pid | Lectura pública existente; respeta bloqueos con sesión |
| GET | /multimedia/comunidades/:cid | Lectura pública existente |

Ampliados: `GET /preguntas` (`comunidad`, nuevos tipos, seguimientos y recomendaciones); `POST /preguntas` (`id_comunidad`, `archivos`); borrador y detalle; `GET /api/usuarios/usuarios/:id/perfil`, `/actividad` y votos personales incorporan datos de comunidad/medios. Las rutas de los tres microservicios se conservan. Las restricciones de publicación y comentarios se aplican también en BD.

## 8. Pruebas y verificación pendiente

Pruebas realizadas en entorno aislado sin credenciales de producción:
- Python: `python -X utf8 -m unittest discover -s backend/tests -p 'test_*.py'` — 165 contabilizadas, 140 superadas, 25 omitidas por dependencias no disponibles, 0 fallos en ejecutadas. Se añadieron 18 pruebas aisladas de validaciones, cuotas, roles, adjuntos, tipos y filtros. El módulo 1 completo necesita dependencias HTTP que aquí no están disponibles.
- Node: 17/17 pruebas existentes del cliente HTTP y clasificación de actividad.
- `compileall` Python correcto; comprobación sintáctica de 28 scripts JS/Vue correcta; análisis de CSS sin errores sintácticos detectados.
- `npm ci --offline` falló por falta de Vue Router en caché; `npm run build` no pudo ejecutarse porque Vite no está instalado. No se han compilado ni probado las plantillas Vue en navegador. No se ejecutaron pruebas SQL, llamadas a Storage o integración con PostgreSQL. Las pruebas aisladas usan mocks y AST, no constituyen verificación de la BD.

### Validación antes de producción

- Ejecutar `backend/tests/comunidades_integracion.sql` únicamente en una BD de pruebas, después de 010/011. Incluye rollback y pruebas de restricciones con dos usuarios. No se ejecutó aquí.
- Crear comunidad pública y restringida con una cuenta. Intentar nombres duplicados. En una segunda cuenta: unirse, abandonar, solicitar ingreso y comprobar que no puede publicar, responder o comentar hasta ser aprobada en la restringida. Probar directamente la API además de la interfaz. Intentar cambiar rol ajeno y moderar otra comunidad. Confirmar 403.
- Probar comunidad en búsqueda, recomendaciones, Siguiendo, perfil y categoría, sin duplicados. Confirmar que funcionan feed, historial y votos anteriores. Revisar las pestañas del perfil y navegabilidad responsive.
- Subir JPG, PNG, WebP y MP4 de prueba. Comprobar compresión, arrastre, progreso, carrusel, video y renovación de enlace. Probar icono/portada, retiro y sustitución. Revisar metadatos en SQL y tamaño/visibilidad en Storage. Verificar que no se envía el archivo a Flask. Probar cancelación, archivo inválido, reserva ajena, límites, cuotas simultáneas, intento de sobrescritura y expiración. Verificar limpieza después de vencer el plazo y que no se borren objetos adjuntos activos. Confirmar el acceso directo sin firma está denegado y que no se expone service_role en DevTools. La seguridad de Storage y la compatibilidad REST deben validarse realmente.
- Validar estado de recursos y transferencia en Supabase. No publicar contenido privado: esa capacidad permanece deshabilitada.

## 9. Vercel (cuando exista autorización)

Primero validar un deployment Preview conectado a base de pruebas y sus cuatro buckets. En Settings → Environment Variables añade `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` como secretos del servidor, además de los valores ya existentes de `DATABASE_URL` y `JWT_SECRET`. No usar `VITE_` ni cambiar vercel.json. Solo después de confirmar pruebas, respaldar y aplicar las migraciones pendientes en la BD productiva con autorización, configurar los buckets privados productivos y sus variables para Production, subir los cambios a la rama de despliegue y verificar Preview/Production. No se realizó ninguno de estos pasos externos. Conservar una copia del ZIP anterior y del esquema antes de actualizar.

## 10. Archivos

Lista comparada con el ZIP auditado anterior:

- Nuevo: `COMUNIDADES_Y_MULTIMEDIA.md`
- Modificado: `README.md`
- Modificado: `backend/app_preguntas.py`
- Nuevo: `backend/database/migrations/010_comunidades.sql`
- Nuevo: `backend/database/migrations/011_multimedia.sql`
- Modificado: `backend/extensions.py`
- Nuevo: `backend/routes/comunidades.py`
- Nuevo: `backend/routes/multimedia.py`
- Modificado: `backend/routes/preguntas.py`
- Modificado: `backend/routes/usuarios.py`
- Nuevo: `backend/tests/comunidades_integracion.sql`
- Modificado: `backend/tests/test_auditoria_correcciones.py`
- Nuevo: `backend/tests/test_comunidades_multimedia.py`
- Modificado: `backend/tests/test_feed_compacto.py`
- Modificado: `backend/tests/test_modulo4.py`
- Modificado: `backend/tests/verificar_servicios.py`
- Modificado: `frontend/src/components/BarraNavegacion.vue`
- Nuevo: `frontend/src/components/CargaMultimedia.vue`
- Nuevo: `frontend/src/components/CrearComunidad.vue`
- Modificado: `frontend/src/components/MenuLateral.vue`
- Nuevo: `frontend/src/components/MultimediaPublicacion.vue`
- Modificado: `frontend/src/router/index.js`
- Modificado: `frontend/src/services/api.js`
- Modificado: `frontend/src/style.css`
- Modificado: `frontend/src/views/BuscarView.vue`
- Nuevo: `frontend/src/views/ComunidadesView.vue`
- Modificado: `frontend/src/views/HomeView.vue`
- Modificado: `frontend/src/views/PerfilView.vue`
- Modificado: `frontend/src/views/PreguntaView.vue`
- Modificado: `frontend/tests/api.test.mjs`
