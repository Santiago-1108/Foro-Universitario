-- Ejecutar después de 001 y 002, primero en una base de pruebas.
BEGIN;
ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS biografia VARCHAR(500) NOT NULL DEFAULT '';
ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS avatar_url TEXT;
CREATE TABLE IF NOT EXISTS public.seguimientos_usuarios (
 id_seguidor BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_seguido BIGINT NOT NULL REFERENCES public.usuarios(id),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY (id_seguidor,id_seguido), CHECK (id_seguidor <> id_seguido)
);
CREATE TABLE IF NOT EXISTS public.seguimientos_categorias (
 id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_categoria BIGINT NOT NULL REFERENCES public.categorias(id),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY (id_usuario,id_categoria)
);
ALTER TABLE public.seguimientos_usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seguimientos_categorias ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS ix_seguimientos_usuario_seguido ON public.seguimientos_usuarios(id_seguido);
CREATE INDEX IF NOT EXISTS ix_seguimientos_categoria ON public.seguimientos_categorias(id_categoria);
CREATE INDEX IF NOT EXISTS ix_preguntas_autor_activas ON public.preguntas(id_usuario,fecha_creacion DESC,id DESC) WHERE fecha_eliminacion IS NULL;
CREATE INDEX IF NOT EXISTS ix_respuestas_autor_activas ON public.respuestas(id_usuario,fecha_creacion DESC,id DESC) WHERE fecha_eliminacion IS NULL;
CREATE INDEX IF NOT EXISTS ix_comentarios_autor_activos ON public.comentarios(id_usuario,fecha_creacion DESC,id DESC) WHERE fecha_eliminacion IS NULL;
COMMIT;
