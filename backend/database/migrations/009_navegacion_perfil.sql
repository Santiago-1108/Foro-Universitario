-- Después de 001-008; ejecutar primero en pruebas.
BEGIN;
ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS portada_url VARCHAR(2048);
CREATE TABLE IF NOT EXISTS public.historial_preguntas (
 id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_pregunta BIGINT NOT NULL REFERENCES public.preguntas(id),
 fecha_visita TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(id_usuario,id_pregunta)
);
CREATE INDEX IF NOT EXISTS ix_historial_usuario_fecha ON public.historial_preguntas(id_usuario,fecha_visita DESC);
ALTER TABLE public.historial_preguntas ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.historial_preguntas FROM PUBLIC, anon, authenticated;
COMMIT;
