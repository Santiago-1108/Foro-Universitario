-- Ejecutar después de 001-007. No cambia filas, credenciales ni tablas existentes.
-- Esta aplicación usa exclusivamente Flask y la conexión PostgreSQL de backend.
-- Si existe otro cliente que usa la Data API de Supabase para estas tablas,
-- revisar los permisos con su responsable antes de ejecutar.
BEGIN;
ALTER TABLE public.usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.preguntas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.respuestas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comentarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.votos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.usuarios, public.categorias, public.preguntas, public.respuestas,
 public.comentarios, public.votos, public.votos_encuesta, public.borradores,
 public.seguimientos_usuarios, public.seguimientos_categorias, public.preguntas_guardadas,
 public.preguntas_ocultas, public.bloqueos_usuarios, public.notificaciones,
 public.reportes, public.historial_moderacion, public.conversaciones, public.mensajes
 FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.foro_hay_bloqueo(BIGINT,BIGINT) FROM PUBLIC, anon, authenticated;
COMMIT;
