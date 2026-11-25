-- Ejecutar después de 001-006, primero en una base de pruebas.
BEGIN;
CREATE TABLE IF NOT EXISTS public.conversaciones (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 usuario_a BIGINT NOT NULL REFERENCES public.usuarios(id),
 usuario_b BIGINT NOT NULL REFERENCES public.usuarios(id),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK (usuario_a < usuario_b), UNIQUE(usuario_a,usuario_b)
);
CREATE TABLE IF NOT EXISTS public.mensajes (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_conversacion BIGINT NOT NULL REFERENCES public.conversaciones(id),
 id_emisor BIGINT NOT NULL REFERENCES public.usuarios(id),
 contenido VARCHAR(2000) NOT NULL CHECK (length(btrim(contenido)) BETWEEN 1 AND 2000),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 fecha_lectura TIMESTAMPTZ
);
ALTER TABLE public.conversaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mensajes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.conversaciones, public.mensajes FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE public.conversaciones_id_seq, public.mensajes_id_seq FROM PUBLIC, anon, authenticated;
CREATE INDEX IF NOT EXISTS ix_conversaciones_b ON public.conversaciones(usuario_b,usuario_a);
CREATE INDEX IF NOT EXISTS ix_mensajes_conversacion ON public.mensajes(id_conversacion,id DESC);
CREATE INDEX IF NOT EXISTS ix_mensajes_no_leidos ON public.mensajes(id_conversacion,id) WHERE fecha_lectura IS NULL;
CREATE INDEX IF NOT EXISTS ix_mensajes_emisor_fecha ON public.mensajes(id_emisor,fecha_creacion DESC);
-- Defensa adicional: un emisor siempre debe pertenecer a su conversación.
CREATE OR REPLACE FUNCTION public.foro_validar_emisor_mensaje() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.conversaciones c WHERE c.id=NEW.id_conversacion AND NEW.id_emisor IN (c.usuario_a,c.usuario_b)) THEN
  RAISE EXCEPTION 'Emisor ajeno a la conversación' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.foro_validar_emisor_mensaje() FROM PUBLIC, anon, authenticated;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.mensajes'::regclass AND tgname='foro_validar_emisor' AND NOT tgisinternal) THEN
  CREATE TRIGGER foro_validar_emisor BEFORE INSERT OR UPDATE OF id_conversacion,id_emisor ON public.mensajes
   FOR EACH ROW EXECUTE FUNCTION public.foro_validar_emisor_mensaje();
 END IF;
END $$;
COMMIT;
