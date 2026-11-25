# Optimización integral de UX/UI

## Base y alcance

Se parte de `foro_comunidades_multimedia.zip` con todos los archivos de `foro_correccion_storage.zip` aplicados. Esta entrega modifica exclusivamente frontend y documentación; el backend, las 11 migraciones, las dependencias, el dispatcher y la configuración de Vercel son idénticos a esa base. No se ha efectuado ninguna operación sobre producción.

No se recibieron las ocho nuevas capturas mencionadas en la solicitud. La revisión se basó en los componentes existentes, las capturas anteriores y el comportamiento deducible del código. No se ha reproducido la aplicación completa en el navegador.

## Cambios

- Creación de comunidad: diálogo nativo con encabezado y cierre, progreso por segmentos, pie fijo dentro del diálogo y contenido desplazable; categorías con iconos, filas de tipo con radio de tamaño normal, vista previa de nombre, identificador, temática, descripción y las imágenes locales o URL seleccionadas. Los archivos se mantienen montados al retroceder de paso; se confirma antes de descartarlos. La comunidad privada sigue deshabilitada.
- Personalización: selector de origen para cada imagen, vista previa y conservación del botón Pegar URL del último parche. Se envía solamente el adjunto elegido; el archivo conserva sus validaciones y autorización de Storage.
- Directorio y detalle: tarjetas de exploración, encabezado con portada y avatar, botones compactos, menú de acciones, feed existente y panel de información/normas/moderadores. Se reutilizan clases de tarjetas y el componente MultimediaPublicacion; el feed de inicio sigue siendo el destino para las interacciones completas. No se ha añadido otra API ni se ha extraído el componente completo de publicación, que todavía está integrado en HomeView.
- Administración: secciones de información, apariencia, normas, miembros, solicitudes, moderadores y moderación. Se conservan los métodos y permisos. La sección Moderación remite a los controles ya existentes del feed. No se muestran acciones no soportadas. El formulario comparte un guardado de los campos existentes. Se solicita confirmación antes de expulsar/rechazar miembros o descartar archivos seleccionados al recargar la administración.
- Publicación: destinos en rejilla adaptable, cinco pestañas de tipo (incluye modo URL dentro de Imágenes), título/contenido, etiquetas, borradores en un menú y acción principal Publicar. Los selectores de imágenes y video conservan su estado mientras se cambia de tipo. Recuperar borrador o cancelar con archivos pide confirmación. Los archivos locales no se guardan en los borradores persistentes: se conserva el comportamiento anterior y se informa al usuario.
- Carga: componente reutilizable con zona de arrastre, selector personalizado, nombre, tamaño, miniatura, progreso y retirada. Mismas rutas, cuotas, compresión, MIME y llamadas de verificación. No se han añadido cargas de avatar/portada al perfil de usuario, que sigue utilizando su mecanismo anterior.
- Limpieza: se retira de todos los formularios de carga y se traslada a Configuración del perfil propio → Almacenamiento personal → Liberar espacio. La API existente solo permite limpiar cargas vencidas del usuario autenticado; no se convierte en una operación administrativa global ni se cambia su autorización. Se mantiene la limpieza manual y su límite por llamada.
- Estilos compartidos, sin cambiar los tokens existentes: modo claro y oscuro, botones, iconos, espaciados, rejillas adaptables, foco y tamaños de controles. Los apartados no relacionados (notificaciones, mensajes, login, búsqueda, administración global y detalle) conservan sus plantillas; reciben únicamente estilos compartidos cuando usan los componentes modificados. No se realizó una auditoría visual de todas esas vistas en ejecución.

## Archivos frontend

- `frontend/src/components/CrearComunidad.vue`
- `frontend/src/components/CargaMultimedia.vue`
- `frontend/src/components/GestionAlmacenamiento.vue` (nuevo)
- `frontend/src/components/IconoForo.vue`
- `frontend/src/components/MenuLateral.vue`
- `frontend/src/components/MultimediaPublicacion.vue`
- `frontend/src/views/ComunidadesView.vue`
- `frontend/src/views/HomeView.vue`
- `frontend/src/views/PerfilView.vue`
- `frontend/src/style.css`

## Pruebas reales

- Python: 175 pruebas registradas, 150 aprobadas, 25 omitidas por ausencia de Flask/psycopg2 y dependencias, 0 fallidas.
- JavaScript: 17/17 aprobadas con `node --test tests/*.test.mjs`.
- Node `--check`: scripts de 22 componentes Vue y archivos JS del frontend sin errores sintácticos; plantillas comprobadas por balance de etiquetas (no equivale a compilación Vue).
- CSS: análisis de nivel superior con tinycss2 sin errores; 648 reglas antes de los últimos ajustes menores.
- Chromium: estructura HTML de prueba con las clases nuevas y el CSS real, 320, 375, 768, 1024 y 1440 px, modo claro y oscuro: sin desbordamiento horizontal de la estructura y modal, pie del modal visible. No es una captura ni una prueba de extremo a extremo de Vue.
- Comparación byte por byte: backend, migraciones, dispatcher, package.json, package-lock.json, vite.config.js y vercel.json intactos respecto de la base con parche Storage.
- `npm ci --offline`: no está disponible vue-router en la caché. Intento normal de instalación agotó el tiempo. `npm run build`: Vite no disponible. Por tanto no se declara compilación correcta ni ausencia de errores de consola en la aplicación real.
- Pendiente: probar creación/edición de comunidades, subida real, borradores, permisos, interacciones y responsive en la aplicación Vue ejecutada contra una BD de pruebas. No se han conectado credenciales ni ejecutado migraciones.

## Instalación local

1. Detener frontend (`Ctrl+C`), hacer copia de seguridad y extraer el ZIP de actualización en la raíz `foro2.0`, sobrescribiendo los archivos incluidos. No eliminar `.venv` ni `node_modules`.
2. Si los tres microservicios ya ejecutan la versión con la última corrección de Storage, no es necesario reiniciarlos. Si se reemplaza el proyecto completo o son de otra versión, reiniciar los tres.
3. Desde `frontend`, ejecutar `node --test tests/*.test.mjs` y `npm run build`. Si falta una dependencia, utilizar `npm ci` en el entorno habitual.
4. Iniciar Vite mediante `npm run dev -- --host 127.0.0.1 --port 5173 --strictPort`.
5. Desde la raíz, `.\.venv\Scripts\python.exe backend/tests/verificar_servicios.py --puerto-frontend 5173`.
6. Abrir http://127.0.0.1:5173 y recargar con Ctrl+F5. Probar el flujo de 4 pasos, navegación atrás, selección URL y archivo, creación de publicación, cambio entre tipos, recuperación de borrador, edición y gestión de miembros, ambos temas y móvil. Probar limpieza solo en el perfil propio con archivos de pruebas que hayan vencido.

No requiere migraciones, nuevas variables o buckets. No desplegar hasta validar la compilación y las pruebas manuales. La configuración de Vercel permanece intacta.
