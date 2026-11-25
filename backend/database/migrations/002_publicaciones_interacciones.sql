-- Ejecutar después de 001; primero en una base de pruebas. No elimina datos.
BEGIN;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS tipo VARCHAR(10) NOT NULL DEFAULT 'texto';
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS recurso_url TEXT;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS opciones_encuesta JSONB;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS fecha_edicion TIMESTAMPTZ;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS fecha_eliminacion TIMESTAMPTZ;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS id_respuesta_aceptada BIGINT;
ALTER TABLE public.respuestas ADD COLUMN IF NOT EXISTS fecha_eliminacion TIMESTAMPTZ;
ALTER TABLE public.comentarios ADD COLUMN IF NOT EXISTS id_comentario_padre BIGINT;
ALTER TABLE public.comentarios ADD COLUMN IF NOT EXISTS fecha_eliminacion TIMESTAMPTZ;
CREATE UNIQUE INDEX IF NOT EXISTS ix_respuestas_id_pregunta ON public.respuestas(id,id_pregunta);
CREATE UNIQUE INDEX IF NOT EXISTS ix_comentarios_id_respuesta ON public.comentarios(id,id_respuesta);
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.preguntas'::regclass AND conname='preguntas_tipo_valido') THEN
  ALTER TABLE public.preguntas ADD CONSTRAINT preguntas_tipo_valido CHECK (tipo IN ('texto','imagen','enlace','encuesta'));
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.preguntas'::regclass AND conname='preguntas_respuesta_aceptada_fk') THEN
  ALTER TABLE public.preguntas ADD CONSTRAINT preguntas_respuesta_aceptada_fk FOREIGN KEY (id_respuesta_aceptada,id) REFERENCES public.respuestas(id,id_pregunta);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.comentarios'::regclass AND conname='comentarios_padre_fk') THEN
  ALTER TABLE public.comentarios ADD CONSTRAINT comentarios_padre_fk FOREIGN KEY (id_comentario_padre,id_respuesta) REFERENCES public.comentarios(id,id_respuesta);
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS public.votos_encuesta (
 id_pregunta BIGINT NOT NULL REFERENCES public.preguntas(id),
 id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 opcion SMALLINT NOT NULL CHECK (opcion BETWEEN 0 AND 5),
 PRIMARY KEY(id_pregunta,id_usuario)
);
CREATE TABLE IF NOT EXISTS public.borradores (
 id_usuario BIGINT PRIMARY KEY REFERENCES public.usuarios(id),
 datos JSONB NOT NULL,
 fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.votos_encuesta ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.borradores ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS ix_preguntas_activas_fecha ON public.preguntas(fecha_creacion DESC,id DESC) WHERE fecha_eliminacion IS NULL;
CREATE INDEX IF NOT EXISTS ix_comentarios_padre ON public.comentarios(id_comentario_padre);
COMMIT;
