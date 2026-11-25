# Auditoría y correcciones — foro universitario

Base: `foro_final_compacto.zip`. Esta entrega conserva Vue 3, Flask, PostgreSQL/Supabase, Vercel, los tres servicios, la paleta, las nueve migraciones existentes y las rutas de negocio. No se accedió a la base de datos del usuario ni se ejecutaron escrituras, migraciones o despliegues.

## 1. Diagnóstico de las capturas

| Problema | Evidencia y causa | Corrección |
|---|---|---|
| Para ti / Recomendadas: «Filtros o paginación inválidos» | La petición construida en HomeView usa `orden=para_ti`, `vista=todas`, `limite=21`, `offset=0`, y los filtros opcionales vacíos. Ejecuté `_filtros_feed` extraída de cada ZIP: la versión final inicial y la versión de navegación rechazan esa petición; la compacta la acepta. El mensaje es compatible con ejecutar un Flask anterior. No se dispone de los procesos ni registros HTTP del equipo para confirmarlo como causa efectiva. | Se mantiene el contrato correcto de la versión compacta, se añade diagnóstico de revisión de API y de cada campo inválido, y un botón Reintentar. Reiniciar desde la carpeta actual es imprescindible. |
| Historial: mismo mensaje | La consulta usa `vista=historial`, `limite=21`, `offset=0`. La versión final inicial la rechaza; navegación y compacta la admiten. La consulta de la versión actual restringe por JWT, ordena por fecha de visita y devuelve `[]` con HTTP 200 cuando está vacío. | Orden `reciente` explícito en el cliente (el servidor conserva el orden por fecha de visita), errores diferenciados y verificación de la revisión del servicio. |
| Votos positivos/negativos, Respuestas: «Error en la petición» | La URL actual es `GET /api/usuarios/usuarios/perfil/votos?signo=1&tipo=respuesta&offset=0`. La versión final inicial no registra esta ruta; navegación y compacta sí. La compacta valida tipo y signo antes de paginar y consulta votos sobre preguntas o respuestas mediante UNION ALL. La captura no muestra código HTTP: un 404 por versión anterior o un 500 SQL son posibilidades, no confirmaciones. | Se conserva la ruta correcta, se comprueban ambos signos y tipos y se devuelve diagnóstico HTTP específico, incluso si la respuesta antigua era HTML. No se admiten votos sobre comentarios porque la tabla original solo admite preguntas/respuestas. |
| Recorte del perfil y desplazamiento | El CSS contenía offsets fijos distintos (64, 104, 110 px) para una barra cuyo alto varía y un breakpoint por ancho de ventana, no por ancho de contenido. | Altura de barra medida con ResizeObserver, variables compartidas, límites de ancho y cuadrícula ajustada al espacio disponible. La navegación y las pestañas siguen funcionando; solo estas últimas pueden tener scroll horizontal interno. |

La reproducción de validadores confirma incompatibilidad entre versiones, no cuál proceso se encuentra ejecutándose en el PC. El registro previo del usuario mostraba que Vite abrió 5174 porque 5173 estaba ocupado: esto refuerza la necesidad de cerrar instancias antiguas. No se ha demostrado un fallo de SQL real de los tres endpoints; no se introducen cambios de consulta sin evidencia. Si el error continúa después del reinicio y del diagnóstico, capturar el estado HTTP y el error del servidor es el siguiente paso.

## 2. Correcciones adicionales

- El cliente HTTP conserva estado y mensaje del servidor, diferencia errores de conexión, respuestas no JSON, cancelaciones y errores HTTP. Una lista vacía o un JSON `null` legítimo no se confunden con fallos. No se limpian datos ni se altera la sesión por errores distintos de 401; se conserva la protección frente a respuestas de sesiones anteriores.
- Respuestas JSON para errores HTTP estándar de Flask, conservando cabeceras HTTP como Allow; el 500 no expone trazas ni secretos. Las excepciones no controladas conservan el registro interno de Flask.
- Se añade revisión de API `compacta-auditoria-1`, cabecera `X-Foro-Revision` y endpoint de diagnóstico sin acceso a la base, sin datos privados ni credenciales. Los errores de rutas nuevas con revisión ausente o diferente sugieren comprobar versión, sin ocultar el error original.
- El estado de carga del perfil se establece antes de vaciar el perfil para evitar disparos de watchers en ese intervalo.
- Se mantiene la identidad visual y se corrige el fondo de los números del ranking en modo oscuro.

## 3. Revisión funcional y alcance

Se inspeccionaron las rutas, prefijos, validaciones y llamadas del cliente de Inicio, Para ti, Siguiendo, Popular, Explorar, categorías y categorías seguidas, búsqueda global, perfil, publicaciones, respuestas, comentarios, votos, guardados, ocultos, historial, mis publicaciones, seguimientos, ranking/karma, notificaciones, mensajes, borradores, configuración, sesión y administración. La revisión es estática y mediante las pruebas disponibles; no equivale a recorrer todos los botones ni probar cada rol con una base real.

- Feed: se mantienen los seis ordenamientos, los filtros y los límites; se comprobó la composición de consultas de las 42 combinaciones de orden/vista con categoría, búsqueda, etiqueta, tipo, estado y paginación. Se verificó la denegación sin sesión de vistas privadas. La consulta no se ejecutó en PostgreSQL real.
- Perfil: se conservan los filtros de actividad anteriores a la paginación. Las pruebas de clasificación JS cubren publicaciones, respuestas, comentarios, general y vacío. El historial y votos personales se consultan según la identidad autenticada; no se acepta un id_usuario ajeno como dueño de los datos privados.
- Votos: se mantienen positivos, negativos y cancelación sobre preguntas y respuestas. Se verifica construcción SQL de ambos signos y tipos; no se añade un sistema de votos de comentarios que no existe en el esquema.
- Búsqueda, roles, CRUD, notificaciones, mensajería y moderación: se repiten las suites acumuladas que son ejecutables; faltan dependencias para las pruebas HTTP reales y no se reproduce interacción desde Vue montado en un navegador.
- Compatibilidad Vercel: no se modifica `api/index.py`, `vercel.json` ni `vite.config.js`; el nuevo endpoint comparte el registro de los servicios existentes y sus prefijos. Validación de despliegue pendiente.

## 4. Archivos y endpoints

| Archivo | Cambio |
|---|---|
| `backend/extensions.py` | Estado de revisión, cabeceras, errores HTTP JSON. |
| `backend/routes/preguntas.py` | Validación por campo y detalle de errores. |
| `frontend/src/services/api.js` | Errores HTTP, red, JSON y diagnóstico de versión. |
| `frontend/src/views/HomeView.vue` | Reintentar listado. |
| `frontend/src/views/PerfilView.vue` | Estado de carga, orden explícito para consultas privadas. |
| `frontend/src/components/BarraNavegacion.vue` | Medición de altura de la barra. |
| `frontend/src/style.css` | Dimensiones, scroll y perfil responsive. |
| `backend/tests/verificar_servicios.py` | Diagnóstico local de solo lectura; nuevo. |
| `backend/tests/test_auditoria_correcciones.py` | Nuevas pruebas de regresión; nuevo. |
| `backend/tests/smoke_http.py` | Ampliación de integración en BD de pruebas para los casos reportados. |
| `frontend/tests/api.test.mjs` | Siete pruebas de errores y respuestas JSON adicionales. |
| `AUDITORIA_Y_CORRECCIONES.md` | Informe nuevo. |

Endpoint nuevo de diagnóstico: `GET /estado-api` en cada microservicio; externamente `/api/usuarios/estado-api`, `/api/foro/estado-api` y `/api/interacciones/estado-api`. Devuelve `revision` y `modulos`, sin conexión SQL. Endpoints existentes conservados: `/preguntas`, `/preguntas/categoria/:id`, `/preguntas/:id/visita`, `/preguntas/historial` (DELETE), `/usuarios/perfil/votos`. No hay nuevas migraciones. No repetir 001–009 si ya se aplicaron. No ejecutar setup.sql sobre una base existente.

## 5. Pruebas y resultados

- Python: `python -m unittest discover -s backend/tests -p 'test_*.py'`: 147 contabilizadas, 122 aprobadas, 25 omisiones (incluye grupos/clases omitidos por dependencias), sin fallos. Siete pruebas nuevas de contrato ejecutadas; cuatro métodos HTTP de la nueva clase quedan pendientes por falta de Flask/psycopg2. Los conteos de Windows con dependencias serán distintos.
- Node: `node --test frontend/tests/*.test.mjs`: 17 aprobadas, 0 fallidas, 0 omitidas.
- Comparación directa de validadores de los tres ZIP: resultados documentados en §1.
- Chromium: se probó el CSS del perfil y cabecera con un fixture HTML estático de las mismas clases, no Vue montado. Ocho anchos (320, 375, 768, 1000, 1101, 1211, 1291, 1440 px), todos sin desbordamiento horizontal de documento o recorte de panel/barra. La validación visual de componentes reales queda pendiente.
- Compilación `npm run build`: intentada; Vite no está instalado en este entorno. Instalación de dependencias Python: intentada, no se encontraron paquetes disponibles. No se ejecutó la prueba de integración con PostgreSQL ni se accedió a producción.
- Sintaxis e integridad de archivos: comprobaciones efectuadas antes de empaquetar.

## 6. Actualización y diagnóstico en Windows

1. Haz copia de tu proyecto local. Cierra con Ctrl+C las terminales que ejecutan Vite y los tres Flask ANTES de copiar los archivos del ZIP de actualización sobre la raíz `foro2.0`. No borres `.venv`, `node_modules`, ni configuración. Si hiciste cambios locales adicionales, compara los archivos antes de sobrescribir.
2. Comprueba que no queden procesos antiguos: `Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 5000,5001,5002,5173,5174 } | Select-Object LocalPort,OwningProcess`. Si aparece algún puerto, identifica el proceso con `Get-Process -Id <PID>` y cierra únicamente el servidor anterior que reconozcas. No termines otros procesos a ciegas.
3. Desde la raíz actual, en tres terminales independientes con las mismas variables de entorno existentes, inicia `.\.venv\Scripts\python.exe backend/app_usuarios.py`, `.\.venv\Scripts\python.exe backend/app_preguntas.py`, `.\.venv\Scripts\python.exe backend/app_interacciones.py`. Flask usa debug=False: no recarga automáticamente el código.
4. Desde `frontend`, ejecuta `npm run dev`. Usa exactamente el puerto que imprime Vite. En una quinta terminal, desde raíz, ejecuta:

```powershell
.\.venv\Scripts\python.exe backend/tests/verificar_servicios.py --puerto-frontend 5173
```

Si Vite inició en 5174, sustituye 5173 por 5174. Debe mostrar los tres servicios directos y mediante proxy como OK y también comprobar las consultas públicas de recomendaciones y categorías. Si falla un estado-api, comprueba la carpeta y el proceso indicado. No utiliza tokens ni modifica registros.

5. Ejecuta pruebas y compilación:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p "test_*.py" -v
cd frontend
node --test tests/api.test.mjs tests/actividad.test.mjs
npm run build
```

6. Prueba manualmente recomendaciones/recientes/popular/tendencias, todas las categorías y Siguiendo; abre una publicación y revisa Historial, vota una publicación y respuesta con ambos signos, revisa cada sección privada, cambia de cuenta y verifica privacidad. Comprueba escritorio y móvil, modo claro/oscuro, y navegar con menú abierto/cerrado. Haz pruebas que creen o modifiquen datos solo en una BD de pruebas.
7. Para una integración real adicional existe `backend/tests/smoke_http.py`: **solo en una base separada de pruebas**. Crea cuentas, contenido y votos de prueba; registra y borra únicamente el historial de una cuenta recién creada, y deja datos de prueba. Sigue las instrucciones de README para ejecutar el dispatcher local en puerto 8000 y pasa `--confirmar-base-de-pruebas`. No ejecutar contra producción.
8. Si continúa un error, abre F12 > Network, reproduce la operación y copia URL (sin token), código HTTP, JSON de respuesta y las últimas líneas de la terminal Flask correspondiente, ocultando datos privados. No hace falta cambiar Supabase por un 400 de validación. Un 500 exige revisar el log y confirmar el esquema/migración 009 en pruebas.
9. Despliegue: no se realizó. Antes de publicar, verifica las pruebas y la compilación en tu PC, comprueba las nueve migraciones ya aplicadas y realiza un preview en Vercel con una base de pruebas. No cambiar credenciales ni configuración existente sin necesidad.
