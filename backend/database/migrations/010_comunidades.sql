-- Aplicar tras 009 en pruebas. Categorías existentes intactas.
BEGIN;
CREATE TABLE IF NOT EXISTS public.comunidades (
 id BIGSERIAL PRIMARY KEY, id_categoria BIGINT NOT NULL REFERENCES public.categorias(id),
 id_propietario BIGINT NOT NULL REFERENCES public.usuarios(id),
 nombre VARCHAR(60) NOT NULL CHECK (length(trim(nombre)) BETWEEN 3 AND 60),
 slug VARCHAR(40) NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9_-]{2,39}$'),
 descripcion VARCHAR(500) NOT NULL, normas VARCHAR(2000) NOT NULL DEFAULT '',
 tipo VARCHAR(12) NOT NULL CHECK(tipo IN ('publica','restringida')),
 icono_url TEXT, portada_url TEXT, fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(id,id_categoria)
);
CREATE UNIQUE INDEX IF NOT EXISTS comunidades_nombre_unico ON public.comunidades(lower(nombre));
CREATE TABLE IF NOT EXISTS public.miembros_comunidades (
 id_comunidad BIGINT NOT NULL REFERENCES public.comunidades(id), id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
 rol VARCHAR(12) NOT NULL CHECK(rol IN ('propietario','moderador','miembro')),
 aprobado BOOLEAN NOT NULL DEFAULT false, fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(id_comunidad,id_usuario)
);
CREATE INDEX IF NOT EXISTS miembros_comunidades_usuario ON public.miembros_comunidades(id_usuario,id_comunidad) WHERE aprobado;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS id_comunidad BIGINT;
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.preguntas'::regclass AND conname='preguntas_comunidad_categoria_fk') THEN
 ALTER TABLE public.preguntas ADD CONSTRAINT preguntas_comunidad_categoria_fk FOREIGN KEY(id_comunidad,id_categoria) REFERENCES public.comunidades(id,id_categoria);
END IF; END $$;
CREATE INDEX IF NOT EXISTS preguntas_comunidad_fecha ON public.preguntas(id_comunidad,fecha_creacion DESC,id DESC);
ALTER TABLE public.comunidades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.miembros_comunidades ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.comunidades,public.miembros_comunidades FROM PUBLIC,anon,authenticated;
REVOKE ALL ON SEQUENCE public.comunidades_id_seq FROM PUBLIC,anon,authenticated;
-- Defensa adicional en las escrituras: las tres apps comparten la BD.
CREATE OR REPLACE FUNCTION public.foro_comunidad_permite(p_comunidad BIGINT,p_usuario BIGINT) RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
 SELECT p_comunidad IS NULL OR EXISTS(SELECT 1 FROM public.comunidades c WHERE c.id=p_comunidad AND (c.tipo='publica' OR EXISTS(SELECT 1 FROM public.miembros_comunidades m WHERE m.id_comunidad=c.id AND m.id_usuario=p_usuario AND m.aprobado)));
$$;
CREATE OR REPLACE FUNCTION public.foro_validar_participacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid BIGINT;
BEGIN
 IF TG_TABLE_NAME='preguntas' THEN cid:=NEW.id_comunidad;
 ELSIF TG_TABLE_NAME='respuestas' THEN SELECT id_comunidad INTO cid FROM public.preguntas WHERE id=NEW.id_pregunta;
 ELSE SELECT p.id_comunidad INTO cid FROM public.preguntas p JOIN public.respuestas r ON r.id_pregunta=p.id WHERE r.id=NEW.id_respuesta;
 END IF;
 IF NOT public.foro_comunidad_permite(cid,NEW.id_usuario) THEN RAISE EXCEPTION 'Participación no autorizada en comunidad' USING ERRCODE='42501'; END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER foro_comunidad_pregunta BEFORE INSERT ON public.preguntas FOR EACH ROW EXECUTE FUNCTION public.foro_validar_participacion();
CREATE OR REPLACE TRIGGER foro_comunidad_respuesta BEFORE INSERT ON public.respuestas FOR EACH ROW EXECUTE FUNCTION public.foro_validar_participacion();
CREATE OR REPLACE TRIGGER foro_comunidad_comentario BEFORE INSERT ON public.comentarios FOR EACH ROW EXECUTE FUNCTION public.foro_validar_participacion();
REVOKE ALL ON FUNCTION public.foro_comunidad_permite(BIGINT,BIGINT),public.foro_validar_participacion() FROM PUBLIC,anon,authenticated;
COMMIT;
