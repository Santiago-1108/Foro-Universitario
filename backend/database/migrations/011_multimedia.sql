-- Ejecutar tras 010. Los buckets se configuran desde Storage, no mediante escrituras SQL.
BEGIN;
ALTER TABLE public.preguntas DROP CONSTRAINT IF EXISTS preguntas_tipo_valido;
ALTER TABLE public.preguntas ADD CONSTRAINT preguntas_tipo_valido CHECK(tipo IN ('texto','imagen','enlace','encuesta','multimedia','video'));
CREATE TABLE IF NOT EXISTS public.archivos_foro (
 id UUID PRIMARY KEY, id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_pregunta BIGINT REFERENCES public.preguntas(id),
 id_comunidad BIGINT REFERENCES public.comunidades(id),
 bucket TEXT NOT NULL CHECK(bucket IN ('foro-imagenes','foro-videos','foro-iconos','foro-portadas')),
 ruta TEXT NOT NULL UNIQUE, mime TEXT NOT NULL CHECK(mime IN ('image/jpeg','image/png','image/webp','video/mp4')),
 bytes_reservados BIGINT NOT NULL CHECK(bytes_reservados BETWEEN 1 AND 10000000),
 bytes_reales BIGINT CHECK(bytes_reales BETWEEN 1 AND bytes_reservados),
 estado TEXT NOT NULL DEFAULT 'pendiente' CHECK(estado IN ('pendiente','verificado','adjunto','cancelado','eliminado')),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(), expira TIMESTAMPTZ NOT NULL,
 CHECK ((bucket='foro-videos' AND mime='video/mp4' AND bytes_reservados=10000000) OR (bucket='foro-imagenes' AND mime IN ('image/jpeg','image/png','image/webp') AND bytes_reservados=2000000) OR (bucket='foro-iconos' AND mime IN ('image/jpeg','image/png','image/webp') AND bytes_reservados=500000) OR (bucket='foro-portadas' AND mime IN ('image/jpeg','image/png','image/webp') AND bytes_reservados=1000000)),
 CHECK (id_pregunta IS NULL OR id_comunidad IS NULL),
 CHECK (id_comunidad IS NULL OR bucket IN ('foro-iconos','foro-portadas')),
 CHECK (id_pregunta IS NULL OR bucket IN ('foro-imagenes','foro-videos'))
);
CREATE INDEX IF NOT EXISTS archivos_foro_usuario ON public.archivos_foro(id_usuario,estado);
CREATE INDEX IF NOT EXISTS archivos_foro_pregunta ON public.archivos_foro(id_pregunta) WHERE estado='adjunto';
CREATE UNIQUE INDEX IF NOT EXISTS archivos_foro_comunidad_unico ON public.archivos_foro(id_comunidad,bucket) WHERE estado='adjunto' AND id_comunidad IS NOT NULL;
ALTER TABLE public.archivos_foro ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.archivos_foro FROM PUBLIC,anon,authenticated;
COMMIT;
