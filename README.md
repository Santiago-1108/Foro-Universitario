# Foro universitario — versión consolidada (módulo 8)

Comunidad académica inspirada en Reddit en cuanto a funcionalidades. Conserva Vue 3, Flask, PostgreSQL/Supabase, Vercel, la hoja de estilos y los tres microservicios del proyecto original.

**Estado:** candidato para pruebas (no certificado para producción). El código se ha revisado y se han ejecutado pruebas aisladas; faltan la compilación completa, las pruebas HTTP y la validación en PostgreSQL. Consulta `AUDITORIA.md` antes de desplegar.

## Arquitectura y organización

```text
foro2.0 -Entrega/
├── api/index.py                 # DispatcherMiddleware: punto de entrada Vercel
├── backend/
│   ├── app_usuarios.py          # puerto 5000
│   ├── app_preguntas.py         # puerto 5001
│   ├── app_interacciones.py     # puerto 5002
│   ├── config.py               # DATABASE_URL y JWT_SECRET
│   ├── extensions.py           # conexión por petición a PostgreSQL
│   ├── security.py             # autenticación y autorización
│   ├── routes/                 # Blueprints
│   ├── database/setup.sql      # solo instalación en BD vacía
│   ├── database/migrations/    # 001–008
│   └── tests/                  # unitarias y pruebas de integración manuales
├── frontend/
│   ├── src/components/         # componentes Vue reutilizables
│   ├── src/views/              # páginas
│   ├── src/services/           # fetch y sesión
│   ├── src/router/             # Vue Router
│   ├── src/style.css           # estilos originales, sin cambios
│   ├── tests/                  # pruebas del cliente HTTP
│   └── vite.config.js          # proxy de desarrollo existente
├── requirements.txt
├── vercel.json
└── AUDITORIA.md
```

| Servicio | Puerto local | Prefijo a través de Vite y Vercel |
| --- | --- | --- |
| Usuarios, sesión, notificaciones, moderación y mensajes | 5000 | `/api/usuarios` |
| Publicaciones, categorías, borradores, encuestas y guardados | 5001 | `/api/foro` |
| Respuestas, comentarios y votos | 5002 | `/api/interacciones` |
| Frontend Vue | 5173 | `/` |

Vite reenvía las peticiones localmente y `api/index.py` hace el mismo despacho en Vercel. La API usa JSON sobre HTTP, con `Authorization: Bearer <JWT>` para rutas protegidas. Los tres servicios comparten PostgreSQL y la clave JWT. No se usa la Data API de Supabase ni su autenticación; se usa la conexión PostgreSQL desde Flask.

## Funcionalidades acumuladas

| Módulo | Funcionalidades presentes en código |
| --- | --- |
| 1 | Roles reales, validación, paginación, votos idempotentes y consultas parametrizadas |
| 2 | Texto, imágenes/enlaces por URL HTTPS, encuestas, edición, borrado lógico, borrador privado, comentarios anidados, respuesta aceptada y enlace para compartir |
| 3 | Comunidades a partir de categorías, seguimientos, perfil, actividad, karma e insignias |
| 4 | Búsqueda, filtros, etiquetas, tendencias, guardados, ocultamiento, bloqueos y feed personalizado |
| 5 | Notificaciones persistentes, menciones `@ID`, lectura y contador |
| 6 | Reportes, estadísticas administrativas, suspensiones, fijación y cierre de publicaciones, historial de moderación |
| 7 | Conversaciones individuales y mensajes privados, historial, paginación, contador y lectura |
| 8 | Retiro del pago simulado, revocación de sesiones al modificar credenciales o roles, acceso administrativo comprobado, restricciones Data API y pruebas de regresión |

## 1. Preparar el entorno (Windows / PowerShell)

Necesitas Python 3.11 o 3.12 recomendado, Node.js 22.12 o superior compatible con el lockfile de Vite, npm y una base Supabase **de pruebas separada**. No reutilices la base productiva durante las pruebas.

Descomprime el ZIP. Abre PowerShell desde la carpeta que contiene `vercel.json`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Si falla la instalación, comprueba `python --version`, `node --version`, la conectividad y los mensajes de error. No cambies las dependencias ni el lockfile para ocultar el error. No subas `.venv`, `node_modules`, `dist` ni `.env` al repositorio.

## 2. Supabase: preparar una base de pruebas y migrar

### Base nueva (solo pruebas)

1. Crea un proyecto Supabase separado del foro actual. En SQL Editor ejecuta `backend/database/setup.sql` **una única vez** sobre una base vacía. El script crea las seis tablas base y tres categorías iniciales; no crea cuentas ni publicaciones de demostración.
2. Ejecuta las ocho migraciones de la tabla siguiente en orden, una por una. Si una falla, detente y examina el error; no elimines filas ni repitas el setup.
3. Registra cuentas de prueba desde la aplicación una vez iniciada. Para probar administración, asigna el rol `admin` a una cuenta propia verificada mediante SQL Editor de la base de pruebas. Usa su ID real y revisa el resultado antes de confirmar:

```sql
-- Ejemplo exclusivamente para una base de pruebas; sustituir el ID por el real.
BEGIN;
SELECT id, correo, rol FROM public.usuarios WHERE id = 123;
UPDATE public.usuarios SET rol = 'admin', version_sesion = version_sesion + 1
WHERE id = 123 AND NOT suspendido;
SELECT id, correo, rol FROM public.usuarios WHERE id = 123;
-- Ejecutar COMMIT solo si es la cuenta correcta; si no, ROLLBACK.
```

Realiza este bloque en una sesión SQL que permita mantener la transacción y finalízala con `COMMIT;` o `ROLLBACK;`. Cierra sesión y vuelve a iniciar para obtener un JWT vigente. No compartas credenciales de administrador.

### Base existente (tu foro actual)

No ejecutes `setup.sql`. Haz una copia de seguridad verificable de datos y esquema, revisa qué migraciones ya aplicaste y prueba primero las pendientes en una copia separada. No se incluye un sistema automático de historial de migraciones: registra cada archivo aplicado correctamente. Si no sabes qué versión tiene el esquema, inspecciona columnas, tablas y restricciones antes de ejecutar nada.

| Orden | Archivo dentro de `backend/database/migrations/` |
| --- | --- |
| 001 | `001_seguridad_rendimiento.sql` |
| 002 | `002_publicaciones_interacciones.sql` |
| 003 | `003_comunidades_perfiles.sql` |
| 004 | `004_feed_personalizacion.sql` |
| 005 | `005_notificaciones.sql` |
| 006 | `006_moderacion.sql` |
| 007 | `007_mensajeria.sql` |
| 008 | `008_auditoria_seguridad.sql` |

Cada archivo lleva su propia transacción. En SQL Editor abre una consulta nueva, copia un archivo completo, ejecútalo y comprueba el resultado. La migración 008 activa RLS en las tablas base y revoca permisos directos de `PUBLIC`, `anon` y `authenticated` sobre las tablas del foro. El backend actual entra con su conexión PostgreSQL (propietario `postgres`); verifica este supuesto en tu entorno. Si otro sistema utiliza estas tablas mediante la Data API, 008 puede afectarlo: no lo apliques sin revisar esa dependencia. No contiene `DROP TABLE`, `TRUNCATE` ni borrados de registros.

**Advertencia de seguridad:** el setup anterior incluía cuentas de demostración con contraseñas públicas. Quitarlas del script no cambia las cuentas ya creadas en tu Supabase. Antes de publicar, identifica dichas cuentas y, con autorización, cambia sus contraseñas y revoca sesiones o suspende las cuentas no administrativas que no se utilicen. No se modificaron las credenciales existentes en esta entrega.

## 3. Ejecutar localmente

Configura solo las variables de la base de pruebas. En el panel Connect de Supabase obtén el URI PostgreSQL del Transaction pooler, no la URL HTTP de su API. Conserva la conexión y clave productivas sin cambios.

En cada terminal PowerShell que vaya a ejecutar Python, desde la raíz:

```powershell
$env:DATABASE_URL = '<URI PostgreSQL de la base de pruebas>'
$env:JWT_SECRET = '<misma clave aleatoria de pruebas en los tres servicios>'
```

Puedes generar una clave exclusiva de pruebas con `python -c "import secrets; print(secrets.token_hex(32))"`. No publiques ese valor ni lo pegues en el repositorio. Configura SSL en el URI según las instrucciones de Supabase. Las tres terminales deben usar los mismos valores.

Terminal 1:
```powershell
.\.venv\Scripts\python.exe backend/app_usuarios.py
```
Terminal 2:
```powershell
.\.venv\Scripts\python.exe backend/app_preguntas.py
```
Terminal 3:
```powershell
.\.venv\Scripts\python.exe backend/app_interacciones.py
```
Terminal 4:
```powershell
cd frontend
npm run dev
```
Abre `http://localhost:5173`. Si Vite informa otro puerto, usa el que indique. Para comprobar el dispatcher independientemente de Vite, abre otra terminal con variables de pruebas y ejecuta desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m flask --app api/index run --port 8000
```

Prueba en el navegador `http://localhost:8000/api/foro/categorias` y `http://localhost:8000/api/foro/preguntas`. Las rutas protegidas deben rechazar peticiones sin token con 401.

## 4. Pruebas antes del despliegue

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p 'test_*.py' -v
node --test frontend/tests/api.test.mjs
cd frontend
npm run build
cd ..
```

El build debe generar `frontend/dist` sin errores. No basta con ejecutar los tests aislados: en esta entrega no se pudieron instalar Flask, psycopg2 ni Vite en el entorno de revisión. Los tests HTTP unitarios usan una conexión simulada.

En SQL Editor de la **base de pruebas** con 001–008 aplicadas, ejecuta `backend/tests/notificaciones_integracion.sql`, `moderacion_integracion.sql`, `mensajeria_integracion.sql` y `auditoria_permisos.sql`. Los tres primeros insertan datos temporales y hacen rollback; las secuencias pueden avanzar. El último solo consulta permisos.

Para probar las rutas reales con PostgreSQL, en otra terminal, con el dispatcher de puerto 8000 conectado exclusivamente a la base de pruebas:

```powershell
.\.venv\Scripts\python.exe backend/tests/smoke_http.py --confirmar-base-de-pruebas
```

El script crea tres cuentas y contenido de prueba persistente. No usar contra producción ni con `DATABASE_URL` productiva, aunque el servidor esté en localhost. No se ejecutó en esta entrega.

### Checklist manual de aceptación

- [ ] Registrar dos estudiantes y verificar inicio/cierre de sesión y errores de credenciales.
- [ ] Publicar texto, URL de imagen, enlace y encuesta; editar y recargar. Probar borrador vacío y restaurarlo.
- [ ] Cambiar voto +1 a -1, retirarlo y repetir solicitudes sin duplicar votos.
- [ ] Crear respuestas, comentarios anidados y aceptar una respuesta; retirar la solución y borrar lógicamente.
- [ ] Seguir una comunidad y un usuario; verificar karma, ranking y actividad con datos reales.
- [ ] Buscar por título, autor y categoría; ordenar y paginar. Guardar, ocultar y recuperar contenido.
- [ ] Bloquear una cuenta y comprobar que no interactúa ni puede consultar el chat mutuo; verificar el historial tras desbloquear.
- [ ] Recibir y leer avisos en otra sesión; comprobar que las notificaciones ajenas no se pueden marcar.
- [ ] Reportar contenido; revisar como administrador, fijar y cerrar conversación, suspender y reactivar un usuario. Probar que el JWT antiguo no vuelve a funcionar.
- [ ] Enviar mensajes desde dos cuentas; comprobar privacidad con una tercera cuenta y que el contador se actualiza.
- [ ] Cambiar contraseña en una cuenta de prueba vía API con `password_actual`; comprobar que el JWT previo es rechazado.
- [ ] Comparar visualmente todas las vistas con la versión original en escritorio y móvil. Revisar consola, pestaña Network y estados de error.
- [ ] Confirmar que no hay cuentas de ejemplo activas con claves conocidas, ni datos privados accesibles vía Data API.
- [ ] Verificar que la compilación, SQL y pruebas HTTP pasan; revisar recursos y cuotas en Supabase/Vercel.

## 5. Despliegue en el proyecto Vercel existente (solo con autorización)

No se requiere crear proyectos Vercel adicionales. Esta entrega no modifica `vercel.json`, `api/index.py`, `vite.config.js`, `requirements.txt`, `package.json` ni el lockfile.

1. Conserva una copia del código y datos actuales. Usa una rama separada de Git para esta versión; revisa el diff antes del commit. No borres el repositorio original ni copies carpetas de dependencias.
2. En Vercel conserva el proyecto y raíz existentes (la carpeta que contiene `vercel.json`, no `frontend/`). El archivo actual ya define `cd frontend && npm install && npm run build`, `frontend/dist`, y los rewrites a `api/index.py` e `index.html`.
3. Conserva `DATABASE_URL` y `JWT_SECRET` de producción. Si deseas probar mediante un Preview, **debe apuntar a una base de pruebas**, con variables Preview separadas de Production. No cambies valores sin autorización ni permitas que un Preview escriba en la base real. Si la configuración actual no permite esto, prueba localmente y solicita autorización antes de modificarla.
4. Después de las pruebas locales, comprueba el build y la navegación en Preview. Valida que no haya 404 en los prefijos de la API y que recargar una ruta Vue funcione.
5. Solo después de aprobar las verificaciones y contar con respaldo, aplica las migraciones pendientes a producción, en orden, antes de activar el nuevo código. Verifica la compatibilidad del código anterior durante la transición. No apliques `setup.sql`.
6. Autoriza y publica la versión. Verifica en Vercel los logs de la función y las rutas; supervisa conexiones, almacenamiento y uso. No envíes JWT ni URI de conexión en capturas o logs.
7. Si aparece un problema, detén el avance y recupera la versión anterior de código mediante tu mecanismo habitual de rollback en Vercel. Las migraciones son incrementales, pero volver al código anterior no revierte la base; verifica compatibilidad y utiliza el respaldo solo mediante un procedimiento aprobado. No ejecutes SQL destructivo improvisado.

## 6. API de referencia

Los prefijos indicados se usan con Vite o el dispatcher. Las rutas de cada servicio directo no llevan su prefijo externo.

| Método | Ruta externa | Acceso |
| --- | --- | --- |
| POST | `/api/usuarios/auth/registro` y `/auth/login` bajo el mismo prefijo | Público |
| GET | `/api/usuarios/usuarios/yo` | JWT; cuenta propia |
| GET | `/api/usuarios/usuarios/{id}/perfil` | Público, respeta bloqueos cuando hay sesión |
| GET | `/api/usuarios/usuarios/buscar?q=Vue` | Público |
| GET | `/api/usuarios/usuarios/ranking` | Público |
| PUT | `/api/usuarios/usuarios/{id}/seguir` y `/bloquear` | JWT |
| GET | `/api/foro/categorias` | Público |
| PUT | `/api/foro/categorias/{id}/seguir` | JWT |
| GET, POST | `/api/foro/preguntas` | GET público; POST JWT |
| GET, PUT, DELETE | `/api/foro/preguntas/{id}` | GET público; cambios autor/admin |
| GET, PUT, DELETE | `/api/foro/preguntas/borrador` | JWT; privado |
| GET, PUT | `/api/foro/preguntas/{id}/encuesta` | GET público; PUT JWT |
| PUT | `/api/foro/preguntas/{id}/guardar`, `/ocultar`, `/aceptar` | JWT; aceptar autor/admin |
| POST | `/api/interacciones/respuestas`, `/comentarios`, `/votos` | JWT |
| GET | `/api/interacciones/respuestas/pregunta/{id}` | Público |
| GET | `/api/interacciones/comentarios/respuesta/{id}` | Público |
| GET | `/api/usuarios/notificaciones` | JWT; privado |
| PUT | `/api/usuarios/notificaciones/{id}/leer`, `/leer-todas` | JWT; privado |
| POST, GET | `/api/usuarios/moderacion/reportes` | POST JWT; GET admin |
| GET | `/api/usuarios/moderacion/estadisticas`, `/historial` | Admin |
| PUT | `/api/usuarios/moderacion/usuarios/{id}/suspension`, `/preguntas/{id}` | Admin |
| GET | `/api/usuarios/mensajes` | JWT; privado |
| GET, POST | `/api/usuarios/mensajes/{id_otro_usuario}` | JWT; participantes |
| PUT | `/api/usuarios/mensajes/{id_otro_usuario}/leer` | JWT; participantes |

## 7. Solución de errores frecuentes

| Problema | Qué revisar |
| --- | --- |
| `Falta la variable de entorno` | Definir las dos variables en la terminal que ejecuta Python. |
| `invalid dsn` | Usar el URI PostgreSQL, no `https://...supabase.co`. |
| `column ... does not exist` o `relation ... does not exist` | Comprobar que las migraciones 001–008 se ejecutaron en la base conectada. |
| 401 | Token expirado, cuenta suspendida, versión de sesión revocada o JWT_SECRET diferente. Iniciar sesión de nuevo. |
| 403 | Permiso insuficiente o restricción de interacción. Revisar el rol real. |
| 404 en `/api/...` | Revisar dispatcher, prefijos y proxy; no abrir la raíz de un Blueprint sin ruta. |
| 503 | Conexión PostgreSQL, pooler o disponibilidad. |
| `vite: not found` | Ejecutar `npm ci` dentro de `frontend/` y comprobar que termina correctamente. |
| Falla `cd frontend` en Vercel | Revisar la raíz del proyecto, que debe contener la carpeta `frontend`. |

## 8. Alcance y límites

Sin servicios externos adicionales, sin cobros, WebSockets ni notificaciones push. Imágenes y avatares utilizan URL HTTPS; no se implementó subida de archivos a Storage. El foro es público para lectura; registro sin verificación de correo institucional. Las funciones se diseñaron para uso moderado en infraestructura gratuita, no se certifican cuotas ni concurrencia. Consulta `AUDITORIA.md` para los riesgos y pruebas pendientes.

## Refinamiento UX/UI

La actualización de presentación conserva la arquitectura, la paleta, las dependencias y las migraciones de la versión final. Consulta [UX_UI.md](UX_UI.md) para instalar únicamente los archivos modificados, conocer los cambios y repetir las pruebas antes de desplegar. No requiere una migración nueva.

## Actualización de navegación

Consulta [MEJORAS.md](MEJORAS.md) para cambios de interfaz, migración 009 y pruebas de aceptación. Aplicar 009 primero en pruebas.


## Auditoría de compatibilidad y correcciones

Consulta [AUDITORIA_Y_CORRECCIONES.md](AUDITORIA_Y_CORRECCIONES.md) para reiniciar los servicios, comprobar la revisión de API y ejecutar las regresiones. No se necesita una migración adicional.


## Comunidades y multimedia (010–011)

Consulta [COMUNIDADES_Y_MULTIMEDIA.md](COMUNIDADES_Y_MULTIMEDIA.md) para migraciones, buckets, variables, limitaciones y pruebas. Las comunidades privadas todavía no están habilitadas.
