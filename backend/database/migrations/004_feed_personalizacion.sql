-- Ejecutar después de 001, 002 y 003 en una base de pruebas.
BEGIN;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS etiqueta VARCHAR(20) NOT NULL DEFAULT '';
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.preguntas'::regclass AND conname='preguntas_etiqueta_valida') THEN
  ALTER TABLE public.preguntas ADD CONSTRAINT preguntas_etiqueta_valida CHECK (etiqueta IN ('','duda','debate','recurso','anuncio','proyecto'));
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS public.preguntas_guardadas (
 id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_pregunta BIGINT NOT NULL REFERENCES public.preguntas(id),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(id_usuario,id_pregunta)
);
CREATE TABLE IF NOT EXISTS public.preguntas_ocultas (
 id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_pregunta BIGINT NOT NULL REFERENCES public.preguntas(id),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(id_usuario,id_pregunta)
);
CREATE TABLE IF NOT EXISTS public.bloqueos_usuarios (
 id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 id_bloqueado BIGINT NOT NULL REFERENCES public.usuarios(id),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(id_usuario,id_bloqueado), CHECK(id_usuario<>id_bloqueado)
);
ALTER TABLE public.preguntas_guardadas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.preguntas_ocultas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bloqueos_usuarios ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS ix_bloqueos_inverso ON public.bloqueos_usuarios(id_bloqueado,id_usuario);
CREATE INDEX IF NOT EXISTS ix_preguntas_etiqueta_activas ON public.preguntas(etiqueta,fecha_creacion DESC,id DESC) WHERE fecha_eliminacion IS NULL;
-- Función de lectura sin SECURITY DEFINER: respeta RLS y privilegios del invocador.
CREATE OR REPLACE FUNCTION public.foro_hay_bloqueo(a BIGINT,b BIGINT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = pg_catalog, public AS $$
 SELECT EXISTS(SELECT 1 FROM public.bloqueos_usuarios WHERE (id_usuario=a AND id_bloqueado=b) OR (id_usuario=b AND id_bloqueado=a));
$$;
REVOKE ALL ON FUNCTION public.foro_hay_bloqueo(BIGINT,BIGINT) FROM PUBLIC;
-- El backend usa el propietario postgres de la conexión existente.
GRANT EXECUTE ON FUNCTION public.foro_hay_bloqueo(BIGINT,BIGINT) TO postgres;
COMMIT;
