# Mejoras de navegación y experiencia universitaria

Base: `foro_final_ux_ui.zip` (ocho módulos y primera optimización UX/UI). Referencias: cuatro capturas de Reddit proporcionadas: perfil con pestañas y panel lateral, menú de cuenta, feed central con navegación izquierda, y búsqueda con resultados por tipo. Se toma la organización, no su marca, colores, publicidad ni funcionalidades comerciales.

## Cambios implementados en código

- Barra superior con búsqueda global, botón Crear, mensajes, notificaciones y menú de cuenta. Menú lateral fijo en escritorio y desplegable con fondo en móvil, navegación a Inicio, Popular, Explorar, Siguiendo, Guardados, Historial, Mis publicaciones y Administración según rol; categorías y categorías seguidas desde la API. Iconos SVG propios sin paquetes adicionales.
- Feed con pestañas Para ti (feed general) y Siguiendo (feed personalizado existente por seguimientos), guardados y ocultos. Se conserva el buscador local en un panel plegable, filtros, publicación y borrador. Se añaden sugerencias reales de categorías aún no seguidas, acción Seguir, vista Explorar, vista previa de imagen por URL, compartir enlace, autor y fecha al inicio y menú contextual de ocultar/reportar. Se conserva el ranking y el acceso gratuito.
- Perfil con encabezado, navegación por actividad general, publicaciones, respuestas y comentarios, panel lateral de portada, avatar, biografía, rol, antigüedad, estadísticas (incluidas contribuciones), compartir y acciones existentes. Solo el propietario ve guardados, historial, ocultos y votos personales; los votos incluyen publicaciones y respuestas. Los logros y configuración del perfil son accesibles desde el menú. Se conserva el control de bloqueos. La edición de portada y avatar usa URL HTTPS; no se suben archivos.
- Menú de avatar con perfil, edición, borrador, guardados, logros, configuración, tema y cierre de sesión. Cierre por clic fuera, navegación o Escape. El tema es una preferencia de interfaz local, no un dato de negocio. El JWT conserva el almacenamiento anterior.
- Búsqueda global en `/buscar?q=...`: publicaciones, categorías, respuestas/comentarios, multimedia (publicaciones de imagen por URL) y usuarios. Filtros por orden, fecha, votos mínimos y categoría para contenido. Búsqueda literal sin distinguir mayúsculas; categorías se filtran sobre el catálogo real y usuarios usan su endpoint existente. Resultados paginados salvo catálogo de categorías; panel de categorías relacionadas por nombre/descripción. Enlaces a la publicación y anclas de respuesta/comentario. Los comentarios no tienen votos propios: se cuentan como cero en filtro de votos.
- Historial privado de visitas autenticadas a publicaciones, actualizado por POST explícito. Guarda última visita por publicación; borrado voluntario del historial propio con confirmación. No se generan visitas retroactivas. Se conservan restricciones de contenido eliminado, bloqueado u oculto del feed.
- CSS acumulativo: composición de tres columnas en escritorio, diseño adaptativo, superficies y estados de foco existentes, tema oscuro opcional, skeletons de feed/búsqueda, menú contextual, iconos y transiciones con reducción de movimiento. Las demás vistas conservan la optimización anterior. La apariencia real y contraste deben revisarse en navegador.

## Archivos modificados

- `frontend/src/App.vue`, `frontend/src/router/index.js`, `frontend/src/style.css`.
- `frontend/src/components/BarraNavegacion.vue`, `frontend/src/components/HiloComentario.vue`.
- `frontend/src/views/HomeView.vue`, `PerfilView.vue`, `PreguntaView.vue`.
- `backend/routes/preguntas.py`, `backend/routes/usuarios.py`, `backend/routes/auth.py`.
- `README.md`.

Archivos nuevos: `frontend/src/components/MenuLateral.vue`, `IconoForo.vue`, `frontend/src/views/BuscarView.vue`, `backend/database/migrations/009_navegacion_perfil.sql`, `backend/tests/test_navegacion.py`, `MEJORAS.md`.

## API

Se conservan los prefijos de los tres microservicios. No se crea un nuevo servicio.

| Método | Ruta completa | Cambio |
|---|---|---|
| GET | `/api/foro/preguntas` y `/api/foro/preguntas/categoria/:id` | parámetros opcionales `autor`, `dias` (0,1,7,30,365), `min_votos`, vistas `historial`, `positivos`, `negativos` (JWT obligatorio en privadas) |
| POST | `/api/foro/preguntas/:id/visita` | registra o actualiza la visita del usuario autenticado; body `{}` |
| DELETE | `/api/foro/preguntas/historial` | borra solo historial de la sesión autenticada |
| GET | `/api/foro/preguntas/buscar-interacciones` | `q`, `offset`, `orden`, `categoria`, `dias`, `min_votos`; respuestas y comentarios activos con restricciones de bloqueo |
| GET | `/api/usuarios/usuarios/:id/perfil` | portada y cantidad de comentarios |
| PUT | `/api/usuarios/usuarios/perfil` | acepta `portada_url` HTTPS o cadena vacía para quitarla |
| GET | `/api/usuarios/usuarios/:id/actividad` | filtro opcional `tipo`: publicacion, respuesta, comentario |
| GET | `/api/usuarios/usuarios/perfil/votos` | votos vigentes propios de publicaciones y respuestas, `signo=1/-1`, `offset` |
| POST | `/api/usuarios/auth/login` | añade avatar al objeto usuario |
| GET | `/api/usuarios/usuarios/yo` | añade avatar al objeto usuario |

Las nuevas consultas usan parámetros SQL; los órdenes se eligen de una lista cerrada. El historial y los votos privados toman el identificador del JWT, nunca del cliente. No se modifica la configuración del JWT ni de Vercel.

## Migración 009 (obligatoria antes de ejecutar esta versión)

`backend/database/migrations/009_navegacion_perfil.sql` añade `usuarios.portada_url` y `historial_preguntas` con FK, clave primaria compuesta, índice, RLS y revocación de acceso directo a roles públicos de Supabase. No modifica filas existentes. Ejecutar manualmente después de 001–008, primero en una copia de pruebas. No ejecutar `setup.sql` en una base existente. Si el backend anterior se mantiene desplegado, la migración es aditiva; la nueva versión sí necesita la migración para perfiles/historial. Revisar permisos de la conexión de pruebas. No se ha ejecutado SQL contra ninguna base de datos.

## Instalación y pruebas en Windows

Conservar la carpeta `.venv`, `node_modules` y las variables de entorno actuales (de pruebas). Hacer copia del proyecto. Si se usa el ZIP de actualización, extraer su contenido en la raíz de `foro2.0`, verificando cambios locales antes de sobrescribir. Si se usa el completo, extraerlo en otra carpeta y reinstalar con `python -m venv .venv`, ` .\.venv\Scripts\python.exe -m pip install -r requirements.txt` y `npm ci` dentro de frontend.

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p "test_*.py" -v
node --test frontend/tests/api.test.mjs
cd frontend
npm run build
```

Para ejecutar, abrir tres terminales en la raíz, cada una con `DATABASE_URL` y `JWT_SECRET` de pruebas (mismos valores en las tres, sin ponerlos en el frontend), y ejecutar respectivamente:

```powershell
.\.venv\Scripts\python.exe backend/app_usuarios.py
.\.venv\Scripts\python.exe backend/app_preguntas.py
.\.venv\Scripts\python.exe backend/app_interacciones.py
```

En una cuarta terminal dentro de frontend ejecutar `npm run dev`, abrir http://localhost:5173. Puertos 5000/5001/5002 y Vite 5173, con proxy existente.

## Resultados de verificación del entorno de entrega

- Python: 133 pruebas contabilizadas por unittest, 109 superadas, 24 omitidas por dependencias ausentes; sin fallos. 13 nuevas pruebas aisladas de validación/consultas/permisos superadas. Las pruebas del módulo 1 no se pudieron importar por falta de Flask/psycopg2/JWT. Las pruebas aisladas usan cursores simulados, no PostgreSQL real.
- Node: 5/5 pruebas de cliente HTTP superadas.
- Sintaxis Python, 23 scripts JS/Vue y estructura HTML de 17 plantillas Vue: verificación estática correcta. CSS analizado sin errores. No equivale a compilación de Vue.
- `npm run build` intentado; falló por `vite: not found`. No hay dependencias instaladas aquí. La última compilación exitosa comunicada por el usuario era de una versión anterior. No se comprobó la nueva UI en navegador ni se ejecutó migración 009 ni consultas contra PostgreSQL.
- Configuración Vercel, requirements, package.json, package-lock, Vite proxy, dispatcher, config.py y migraciones 001–008: idénticos a la base. CSS anterior conservado como prefijo; se agregan reglas al final. No se agregan dependencias.

## Checklist manual antes de publicar

1. Aplicar 009 en base separada, ejecutar todas las pruebas y compilar. Revisar que las vistas anteriores (admin, mensajería, notificaciones, encuestas y moderación) siguen operativas.
2. Probar el menú lateral en escritorio/tablet/móvil, clic fuera y Escape del menú de usuario, tema claro/oscuro, acceso con y sin sesión y navegación hacia borrador/edición.
3. Crear una publicación, votar y compartir, guardar, ocultar, cambiar filtros, seguir categorías y verificar feed Siguiendo. Recargar y verificar persistencia.
4. Entrar con dos cuentas. En perfil propio, probar portada, avatar, cada pestaña de actividad, votos y guardados. En perfil ajeno, verificar que no aparecen los datos privados incluso agregando `?tab=historial` a la URL. Probar el endpoint privado sin token (401) y verificar que las consultas con token devuelven solo sus propios datos.
5. Abrir varias publicaciones, revisar el historial, volver a visitarlas y confirmar orden. Borrar el historial de una cuenta y comprobar que el de la otra sigue intacto.
6. Buscar contenido real en cada pestaña, usar filtros, comprobar ausencia de resultados, paginación, errores, bloqueos y enlaces a comentarios/respuestas.
7. Revisar anchuras 360/768/1024/1440, contraste y teclado. Corregir cualquier fallo antes de actualizar Vercel. No se ha realizado despliegue ni cambio de producción.

## Pendientes y decisiones de alcance

No se simulan datos de negocio. El feed Para ti sigue siendo el feed general (no recomendaciones por IA); Siguiendo reutiliza el feed por seguimientos. Las sugerencias son categorías no seguidas, no recomendaciones estadísticas. Las imágenes/portadas y multimedia son URLs externas HTTPS, sin carga directa. El historial cubre publicaciones visitadas, no historial de búsquedas ni páginas externas. La configuración nueva organiza perfil, bloqueos/seguimientos e historial, no es un centro completo de contraseña, notificaciones o privacidad. La actividad privada de votos muestra votos actuales, no un registro histórico de cambios. No hay búsqueda difusa ni relevancia por aprendizaje automático. No se añadieron sistema comercial, Premium ni comunidades paralelas. Queda pendiente validar la experiencia real, consistencia de todos los estados de carga y accesibilidad completa en navegador, además de la ejecución SQL. No presentar esta versión como certificada para producción hasta completar la lista anterior.

---

# Refinamiento avanzado: feed compacto, perfil y tema negro

Base: `foro_navegacion_final.zip` (la versión con migración 009). Se conservan los tres microservicios, configuración de Vercel, dependencias, rutas anteriores, tipografía y paleta clara. No se realizaron operaciones en producción.

## Cambios

- Inicio: se retira el contenedor y buscador local; pestañas Para ti y Siguiendo, orden y filtros plegables en una barra. Guardados y Ocultos disponibles en el perfil y menú lateral. El único CTA Crear se encuentra en la barra superior; conserva el editor y los borradores anteriores.
- Búsqueda global: se trasladan etiqueta, estado, tipo y alcance (general, siguiendo, guardados y ocultos) al buscador existente para publicaciones e imágenes.
- Para ti: orden `para_ti` en el endpoint de preguntas, con publicaciones fijadas primero, puntuación basada en votos netos no negativos y número de respuestas, disminución según antigüedad en horas y multiplicador 1.5 para autores o categorías seguidos. Es una heurística explícita, no IA. Sin sesión se aplica la puntuación general. Siguiendo conserva el filtro OR EXISTS previo, sin duplicar filas. La paginación sigue siendo por offset; si cambian votos o fechas durante la navegación puede cambiar el orden entre páginas.
- Densidad: tarjetas y compacta comparten DOM y acciones, con variantes CSS. Preferencia `foro-densidad` local, no información de negocio. Enlaces y encuestas conducen al detalle existente. Votos agrupados, acciones contextuales con permisos y reutilización de los endpoints de moderación.
- Perfil: métricas sin cajas individuales, portada vacía de 38 px, botones compactos y opciones agrupadas. La actividad se sitúa arriba en pantallas pequeñas.
- Pestañas: la consulta original ya contenía un filtro `tipo` antes de paginar. No fue posible reproducir el fallo descrito en navegador. Se refuerza el watcher de la pestaña efectiva, se captura el tipo e ID de cada consulta, se descartan respuestas obsoletas, se reinicia el offset, se filtra defensivamente por tipo y se diferencia el título del hilo padre del extracto de respuesta/comentario. Las vistas de votos muestran publicaciones por defecto y permiten elegir respuestas, conservando esta capacidad anterior.
- Tema oscuro: fondo #000000, barra y menú #0A0A0A, tarjetas #121212, superficies #1A1A1A, hover #242424, bordes #303030, texto #F1F1F1, texto secundario #A6A6A6; turquesa como acento. Se conserva el almacenamiento de preferencia existente y se inicializa en App.vue incluso en login.
- Navegación: menú lateral más denso, scrollbar discreta, retorno del scroll al usar atrás/adelante.

## Archivos

Modificados: `backend/routes/preguntas.py`, `backend/routes/usuarios.py`, `frontend/src/App.vue`, `frontend/src/components/BarraNavegacion.vue`, `IconoForo.vue`, `MenuLateral.vue`, `frontend/src/router/index.js`, `frontend/src/style.css`, `frontend/src/views/BuscarView.vue`, `HomeView.vue`, `PerfilView.vue`, `PreguntaView.vue`, `MEJORAS.md`.

Nuevos: `backend/tests/test_feed_compacto.py`, `frontend/src/utils/actividad.js`, `frontend/tests/actividad.test.mjs`.

## API y base de datos

- `GET /api/foro/preguntas` y `GET /api/foro/preguntas/categoria/:id`: admiten `orden=para_ti`. Los valores anteriores se mantienen. El nuevo orden aplica antes de LIMIT/OFFSET. Las consultas están parametrizadas.
- `GET /api/usuarios/usuarios/perfil/votos`: parámetro opcional `tipo=publicacion|respuesta`. Si no se envía, conserva la respuesta anterior mixta. La identidad se obtiene del JWT.
- No hay endpoints nuevos ni cambios de esquema. Se necesitan las migraciones 001–009 ya incluidas en la versión anterior; si están aplicadas no hay nada que ejecutar en Supabase. No ejecutar setup.sql sobre una base existente.

## Resultados reales

- Python: 140 pruebas descubiertas, 116 superadas, 24 omitidas por ausencia de dependencias, cero fallos en las ejecutadas. Siete pruebas nuevas pasaron (consultas, filtros y privacidad; usan simulación de cursor).
- Node: 10 pruebas superadas, cero fallos (cinco anteriores y cinco de clasificación de actividad).
- Sintaxis: 27 archivos/scripts JavaScript y 17 plantillas Vue con etiquetas balanceadas; sintaxis Python y parseo de reglas CSS correctos. Esto no sustituye al compilador de Vue.
- `npm run build`: no ejecutado con éxito, Vite ausente. `npm ci --offline` falló por paquetes no disponibles en caché. No se probó integración con PostgreSQL real ni interfaz en navegador. No se afirma que se haya reproducido el error del perfil o confirmado su corrección de extremo a extremo.

## Actualización local (PowerShell)

1. Respaldar la instalación y descomprimir el ZIP incremental dentro de la raíz `foro2.0` (sin carpeta adicional). Revisar diferencias si hay cambios propios. No eliminar `.venv` ni `node_modules`.
2. Desde la raíz: ` .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p "test_*.py" -v`.
3. `cd frontend`; `node --test tests/api.test.mjs tests/actividad.test.mjs`; `npm run build`.
4. Reiniciar los tres microservicios Flask (usuarios 5000, foro 5001, interacciones 5002), manteniendo DATABASE_URL y JWT_SECRET. Ejecutar `npm run dev` desde frontend.
5. Abrir http://localhost:5173 y validar en una base de pruebas. No desplegar hasta superar las pruebas.

## Aceptación manual pendiente

- Crear una publicación, responder a otra y comentar en un hilo. Verificar las tres pestañas por separado, incluyendo sección vacía y cambio rápido entre pestañas. Probar otro perfil sin acceso a sus pestañas privadas.
- Seguir y dejar de seguir una categoría y un usuario: Siguiendo debe reflejar cambios; Para ti debe seguir mostrando otras categorías. Verificar usuario invitado, filtros y paginación.
- Cambiar tarjetas/compacta, recargar y comprobar preferencia. Probar votos, guardar, compartir, reporte, editar y moderación con los roles adecuados.
- Probar búsqueda global por tipo, etiqueta, estado y alcance. Probar guardados y ocultos desde sus nuevas entradas.
- Revisar tema negro, contraste, formularios y ventanas modales, menú de cuenta, notificaciones, administración y mensajería. Comprobar escritorio, tablet y móvil; revisar especialmente menús emergentes y scroll.

No se incorporaron servicios externos, nueva dependencia o migración. Las encuestas se siguen votando desde la vista de detalle. Las limitaciones anteriores de subida directa de archivos y las pruebas de capacidad de los planes gratuitos no cambian.
