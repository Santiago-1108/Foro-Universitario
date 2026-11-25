# Actualización UX/UI del foro universitario

## Alcance

Se conserva la paleta original, la familia tipográfica system-ui, la arquitectura Vue 3/Flask/PostgreSQL y los tres microservicios. Se mantienen rutas, llamadas HTTP, datos, permisos, dependencias, migraciones y configuración de Vercel. No se ha accedido a producción. El CSS original se conserva y se amplía al final con reglas de presentación. La única modificación fuera de frontend/src es la corrección UTF-8 de la prueba test_modulo5.py que ya se aplicó en Windows durante la validación del usuario.

## Mejoras por pantalla

- Inicio: buscador con botón en línea en escritorio, filtros en rejilla, restablecimiento de filtros sin cambiar la comunidad o vista elegida, navegación por comunidades, editor antes del buscador con foco en el título, estados de votos y guardados más claros. El ranking mantiene su fórmula y muestra las estrellas solamente a partir de 10 puntos.
- Perfiles: encabezado con avatar, cuadrícula semántica de estadísticas, separación de secciones y enlaces más uniformes.
- Publicación: separación de respuestas, resaltado de la aceptada, barras de encuestas basadas en los votos recibidos, hilos anidados con guía visual y estados de guardado/ocultamiento accesibles.
- Mensajes: bandeja más compacta, indicador de conversación sin leer, mensajes alineados según el emisor y editor separado.
- Administración: pestañas accionables por teclado con aria-pressed, estadísticas en tarjetas y listas flexibles.
- Navegación: estado activo, panel de notificaciones con título, botón Cerrar y resaltado de pendientes. El modal de acceso limita el foco al diálogo mientras está abierto y lo devuelve al cerrar cuando el elemento anterior sigue presente.
- Móvil: controles reorganizados según el ancho, panel de notificaciones ajustado a pantalla, barra no fija para no ocupar demasiado espacio, textos largos ajustables y tamaños de interacción consistentes.

## Actualizar la instalación existente (recomendado)

1. Guarda una copia de tu carpeta actual o crea una rama de Git. Detén Vite.
2. Descomprime `foro_actualizacion_ux_ui.zip` dentro de la raíz del proyecto (donde están backend/ y frontend/). Reemplaza solo los archivos incluidos. No reemplaces `.venv`, `node_modules`, archivos locales de variables ni el repositorio .git. Si has hecho cambios propios desde el ZIP final, revisa el diff antes de sobrescribir.
3. Desde la raíz en PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p "test_*.py" -v
cd frontend
node --test tests/api.test.mjs
npm run build
npm run dev
```

4. Abre la URL que indique Vite. Mantén los tres microservicios en ejecución con las mismas variables de entorno que ya utilizabas. No se requiere una nueva migración SQL ni modificar Supabase o Vercel.

También se entrega `foro_final_ux_ui.zip` como copia completa alternativa; no necesitas ambos ZIP. El ZIP completo parte de la versión final que se compartió en el chat, no de la carpeta de tu computador.

## Validación de esta entrega

- Node: 5/5 pruebas del cliente HTTP superadas.
- Python: 120 pruebas detectadas, 96 superadas, 24 omitidas por dependencias ausentes. El entorno no tiene Flask/psycopg2. No equivale a las 129 pruebas que ejecutaste en tu equipo.
- Revisión estática: 14 plantillas con etiquetas balanceadas; comprobación de sintaxis de archivos JS y scripts Vue con Node; análisis sintáctico CSS correcto. Estas comprobaciones no son una compilación de Vue.
- Vite: no se pudo completar `npm ci` (paquetes no disponibles en caché y la instalación en línea no terminó en el tiempo de ejecución). `npm run build` falla en este entorno porque Vite no está instalado. No se ha validado visualmente el resultado en navegador.
- Comparación con el ZIP anterior: código de backend en ejecución, SQL, package.json, package-lock.json, Vercel y dispatcher intactos. Solo cambian archivos de frontend, documentación y una prueba de codificación.

## Checklist manual antes de desplegar

- Escritorio y móvil (320, 375, 768 y 1280 px): comprobar ausencia de desplazamiento horizontal, texto legible y controles accesibles.
- Inicio: cambiar categorías, buscar, limpiar búsqueda, restablecer filtros, publicar y cancelar con teclado; probar guardados y ocultos.
- Detalle: probar votos, encuestas, respuestas aceptadas, comentarios y reportes.
- Perfil: comprobar métricas, edición, seguimientos y bloqueos.
- Mensajes: enviar y recibir con dos cuentas, marcar como leídos, abrir conversaciones anteriores.
- Administración: verificar pestañas, reportes y estadísticas con datos de prueba.
- Notificaciones y modal: abrir/cerrar con ratón, Escape y teclado; comprobar que el foco vuelve al control y que los avisos no quedan cortados en móvil.
- Confirmar que la nueva compilación termina correctamente antes de actualizar Vercel.
