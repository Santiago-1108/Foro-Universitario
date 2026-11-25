# Auditoría técnica — módulo 8

## Resultado

Se trabajó sobre el ZIP del módulo 7, no sobre Vercel ni Supabase productivos. Esta versión es un **candidato a validación**, no una versión certificada. La revisión abarcó las rutas, SQL, control de sesión, componentes Vue, dependencias declaradas, scripts de prueba y documentación. No fue una auditoría dinámica de seguridad ni una prueba de carga.

## Hallazgos y correcciones

| Prioridad | Hallazgo | Corrección en la copia |
| --- | --- | --- |
| Crítica | El setup creaba usuarios con contraseñas conocidas, incluido administrador. | Se retiraron las cuentas y contenido de ejemplo del script de instalación vacía. Las cuentas existentes no fueron modificadas. |
| Alta | El Premium simulado alteraba el estado local, sin pagos ni autorización. | Se conserva la ruta y diseño base, ahora como información de acceso gratuito. Se retira la activación ficticia. |
| Alta | Modificar contraseña, correo o rol no revocaba el JWT previo y el cambio podía sobrescribir datos concurrentes. | Bloqueo de filas ordenado, revalidación del actor, confirmación de contraseña propia, incremento de versión de sesión. No se permite degradar administradores por esa ruta. |
| Alta | El guard de administración confiaba en datos del navegador. | Consulta `/usuarios/yo` mediante JWT; redirige si el servidor no confirma el rol. El backend sigue siendo la autoridad. |
| Alta | Respuestas HTTP de una sesión anterior podían actualizar una vista tras cambiar de cuenta. | El cliente HTTP descarta respuestas cuyo token ya no coincide; las vistas privadas reaccionan al cierre/cambio de cuenta. |
| Alta | Algunas tablas tenían RLS, pero dependían también de los permisos directos de la Data API. | 008 revoca permisos directos de `PUBLIC`, `anon` y `authenticated` sobre las tablas del foro. Requiere verificar que el backend utiliza la conexión propietaria y que no hay otros clientes. |
| Media | Una URL de redirección podía incluir barras invertidas o caracteres de control. | Se restringe la redirección de login a rutas internas. |
| Media | Contraseñas nuevas podían ser demasiado cortas. | Mínimo 8 caracteres para nuevas cuentas y cambios de clave; no se cambia la clave existente. |
| Media | No había tope global de solicitud JSON. | Límite de 32 KiB y error 413; cabecera `X-Content-Type-Options`. |
| Media | Los procesos locales tenían depuración habilitada. | Se desactiva por defecto, sin cambiar la configuración Vercel. |
| Media | README acumulado con referencias a módulos anteriores, comandos y simulaciones obsoletas. | Guía consolidada de migración, ejecución y validación. |

## Verificación de los requisitos iniciales

| Requisito | Situación |
| --- | --- |
| Arquitectura original | Tres apps Flask y dispatcher existentes; Vue 3 y PostgreSQL. |
| Identidad visual | `style.css` original conservado; las nuevas vistas necesitan revisión visual real. |
| Publicaciones e interacciones | Texto, imagen URL, enlace, encuesta, edición y borrado lógico; votos y comentarios; solución aceptada. |
| Comunidades y perfiles | Basados en categorías; seguimiento, historial, avatar URL, karma e insignias. |
| Feed y preferencias | Búsqueda de texto, usuario y comunidad, ordenamiento, etiquetas, guardados, ocultamiento y bloqueo. |
| Notificaciones | Eventos persistentes vía triggers; menciones con ID; lectura y contador. |
| Moderación | Reportes, suspensiones, estadísticas y gestión administrativa. |
| Mensajes | Conversaciones individuales y lectura; sin adjuntos ni E2EE. |
| Persistencia | Las funciones anteriores están conectadas a SQL, pero requieren validación contra PostgreSQL real. |
| Plan gratuito | Diseño sin servicios nuevos; cuotas y capacidad no verificadas. |
| Producción | No se ejecutaron migraciones, despliegues, ni cambios de credenciales. |

## Riesgos que permanecen y decisiones de alcance

**Antes de publicar:** ejecutar todas las pruebas de `README.md`, comprobar las cuentas heredadas de ejemplo y revisar las variables y permisos. La 008 cambia privilegios, no datos: si otros clientes usan Data API, evaluar impacto primero.

- No se pudo ejecutar Flask/psycopg2, PostgreSQL ni Vite. La sintaxis no garantiza que los Blueprints, consultas, triggers, templates y estilos se integren correctamente. Las pruebas simuladas tampoco sustituyen una prueba funcional.
- Las imágenes y los avatares son enlaces HTTPS externos, sin subida a Supabase Storage. Quien visita contenido puede contactar el servidor externo de la imagen. La subida directa necesitaría decidir límites, validación de archivos, bucket y permisos. No se agregaron credenciales de Storage ni almacenamiento adicional.
- No hay confirmación de correo institucional ni recuperación de contraseña por correo. El registro acepta correos con formato básico; la comunidad es pública para lectura. Si se necesita exclusividad universitaria, acordar y verificar un método de ingreso antes de publicar.
- Los JWT se mantienen en localStorage conforme al diseño original; una vulnerabilidad XSS podría exponerlos. El cierre local no revoca por sí solo un token copiado; cambios sensibles y suspensiones sí revocan sesiones. No hay MFA ni límite completo de intentos de login o reportes. Para exposición pública abierta, reforzar estos controles.
- Los comentarios anidados cuelgan de respuestas, no directamente de otras publicaciones; existe un solo borrador por usuario. Compartir copia el enlace, sin republicar dentro del foro. No hay edición de opciones de encuestas ni múltiples etiquetas por publicación.
- Las notificaciones no reconstruyen eventos históricos ni las menciones introducidas por edición. Se consultan periódicamente, no en tiempo real; no avisan votos negativos. Los mensajes privados no son cifrados de extremo a extremo; los administradores del sistema de base de datos tienen acceso operativo.
- El bloqueo restringe interacciones y visibilidad con sesión, pero no convierte en privado el contenido público. Puede haber condiciones de carrera en solicitudes iniciadas antes de un cambio de permisos; algunas escrituras siguen sin revalidación dentro de la misma transacción.
- El feed está paginado, pero el detalle de publicaciones aún consulta votos y comentarios por respuesta y los listados administrativos pueden crecer. No se midió rendimiento, concurrencia ni consumo de cuotas. Se recomienda probar con datos representativos antes de ampliar usuarios.
- La moderación es global, no por comunidad; suspensiones indefinidas; no hay reglas específicas por comunidad ni permisos delegados. No se añadieron publicidad, monetización ni integraciones externas.
- La política de contraseñas nuevas y la confirmación de cambios sensibles modifican el contrato del endpoint PUT `/usuarios/{id}`: los cambios propios de correo o contraseña requieren `password_actual`. El cambio de nombre no revoca la sesión. No se creó una pantalla nueva de cambio de contraseña.

## Resultados obtenidos en el entorno de revisión

- Python: 120 casos registrados por unittest, 96 superados, 24 omitidos (uno es la omisión del módulo de pruebas HTTP 1). Se ejecutaron los casos aislados de módulos 2 a 8. Las pruebas del módulo 8 aportan 14 casos.
- Node: 5 pruebas del cliente HTTP y redirección, todas superadas.
- Instalación: `pip install -r requirements.txt` no pudo obtener Flask; `npm ci --offline` no encontró los paquetes en caché y el intento de instalación por red no concluyó. `npm run build` produjo `vite: not found`.
- Pendientes: pruebas HTTP con Flask, compilación y renderizado Vue, migraciones PostgreSQL 001–008, pruebas SQL transaccionales y prueba HTTP real `smoke_http.py`. No se contactó Supabase ni Vercel productivos.

Consulta el checklist del README. No autorizar el despliegue definitivo hasta resolver los bloqueos de validación y revisar la seguridad de cuentas existentes.
