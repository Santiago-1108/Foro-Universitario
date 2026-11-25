-- Aplicar después de 001 a 004 en una base de pruebas. No genera avisos retroactivos.
BEGIN;
CREATE TABLE IF NOT EXISTS public.notificaciones (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_destinatario BIGINT NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    id_actor BIGINT NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    tipo VARCHAR(24) NOT NULL CHECK (tipo IN ('respuesta','comentario','mencion','voto','seguidor')),
    id_objeto BIGINT NOT NULL,
    objeto VARCHAR(12) NOT NULL CHECK (objeto IN ('pregunta','respuesta','comentario','usuario')),
    id_pregunta BIGINT REFERENCES public.preguntas(id) ON DELETE CASCADE,
    id_respuesta BIGINT REFERENCES public.respuestas(id) ON DELETE CASCADE,
    id_comentario BIGINT REFERENCES public.comentarios(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_lectura TIMESTAMPTZ,
    CHECK (id_destinatario <> id_actor),
    UNIQUE (id_destinatario, id_actor, tipo, objeto, id_objeto)
);
ALTER TABLE public.notificaciones ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.notificaciones FROM PUBLIC, anon, authenticated;
CREATE INDEX IF NOT EXISTS ix_notificaciones_destino ON public.notificaciones(id_destinatario,id DESC);
CREATE INDEX IF NOT EXISTS ix_notificaciones_no_leidas ON public.notificaciones(id_destinatario,id DESC) WHERE fecha_lectura IS NULL;

-- Funciones internas, sin SECURITY DEFINER. La API conserva su rol PostgreSQL existente.
CREATE OR REPLACE FUNCTION public.foro_crear_notificacion(dest BIGINT, actor BIGINT, clase TEXT,
    objeto_tipo TEXT, objeto_id BIGINT, pregunta BIGINT, respuesta BIGINT, comentario BIGINT)
RETURNS VOID LANGUAGE sql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
    INSERT INTO public.notificaciones(id_destinatario,id_actor,tipo,objeto,id_objeto,id_pregunta,id_respuesta,id_comentario)
    SELECT u.id,actor,clase,objeto_tipo,objeto_id,pregunta,respuesta,comentario
    FROM public.usuarios u WHERE u.id=dest AND u.id<>actor AND NOT public.foro_hay_bloqueo(u.id,actor)
      AND NOT EXISTS (SELECT 1 FROM public.preguntas p WHERE p.id=pregunta AND
          (p.fecha_eliminacion IS NOT NULL OR public.foro_hay_bloqueo(u.id,p.id_usuario)))
      AND NOT EXISTS (SELECT 1 FROM public.respuestas r WHERE r.id=respuesta AND
          (r.fecha_eliminacion IS NOT NULL OR public.foro_hay_bloqueo(u.id,r.id_usuario)))
    ON CONFLICT (id_destinatario,id_actor,tipo,objeto,id_objeto) DO NOTHING;
$$;

-- @ID público del perfil (no correo ni nombre ambiguo). Hasta 10 destinatarios válidos por publicación.
-- Se compara como NUMERIC para que un identificador de 19 dígitos fuera del rango BIGINT no interrumpa la escritura.
CREATE OR REPLACE FUNCTION public.foro_notificar_menciones(contenido TEXT, actor BIGINT,
    objeto_tipo TEXT, objeto_id BIGINT, pregunta BIGINT, respuesta BIGINT, comentario BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE destinatario BIGINT;
BEGIN
    FOR destinatario IN
        SELECT DISTINCT u.id FROM regexp_matches(contenido,
            '(?<![[:alnum:]_@])@([1-9][0-9]{0,18})(?![[:alnum:]_@])', 'g') AS m(partes)
        JOIN public.usuarios u ON u.id::numeric=(m.partes[1])::numeric
        WHERE u.id<>actor AND NOT public.foro_hay_bloqueo(u.id,actor)
        ORDER BY u.id LIMIT 10
    LOOP
        PERFORM public.foro_crear_notificacion(destinatario,actor,'mencion',objeto_tipo,objeto_id,pregunta,respuesta,comentario);
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION public.foro_notificar_contenido() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE destino BIGINT; pregunta BIGINT;
BEGIN
    IF TG_TABLE_NAME='preguntas' THEN
        PERFORM public.foro_notificar_menciones(NEW.titulo || ' ' || NEW.contenido,NEW.id_usuario,'pregunta',NEW.id,NEW.id,NULL,NULL);
    ELSIF TG_TABLE_NAME='respuestas' THEN
        SELECT p.id_usuario INTO destino FROM public.preguntas p WHERE p.id=NEW.id_pregunta AND p.fecha_eliminacion IS NULL;
        PERFORM public.foro_crear_notificacion(destino,NEW.id_usuario,'respuesta','respuesta',NEW.id,NEW.id_pregunta,NEW.id,NULL);
        PERFORM public.foro_notificar_menciones(NEW.contenido,NEW.id_usuario,'respuesta',NEW.id,NEW.id_pregunta,NEW.id,NULL);
    ELSIF TG_TABLE_NAME='comentarios' THEN
        SELECT r.id_pregunta,r.id_usuario INTO pregunta,destino FROM public.respuestas r WHERE r.id=NEW.id_respuesta AND r.fecha_eliminacion IS NULL;
        IF NEW.id_comentario_padre IS NOT NULL THEN
            SELECT c.id_usuario INTO destino FROM public.comentarios c WHERE c.id=NEW.id_comentario_padre AND c.fecha_eliminacion IS NULL;
        END IF;
        IF pregunta IS NOT NULL THEN
            PERFORM public.foro_crear_notificacion(destino,NEW.id_usuario,'comentario','comentario',NEW.id,pregunta,NEW.id_respuesta,NEW.id);
            PERFORM public.foro_notificar_menciones(NEW.contenido,NEW.id_usuario,'comentario',NEW.id,pregunta,NEW.id_respuesta,NEW.id);
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.foro_notificar_voto() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE destino BIGINT; pregunta BIGINT;
BEGIN
    -- Solo votos positivos. No se revela la identidad de quien vota negativamente.
    IF NEW.voto<>1 THEN RETURN NEW; END IF;
    IF TG_OP='UPDATE' THEN
        IF OLD.voto=NEW.voto THEN RETURN NEW; END IF;
    END IF;
    IF NEW.id_pregunta IS NOT NULL THEN
        SELECT p.id_usuario INTO destino FROM public.preguntas p WHERE p.id=NEW.id_pregunta AND p.fecha_eliminacion IS NULL;
        PERFORM public.foro_crear_notificacion(destino,NEW.id_usuario,'voto','pregunta',NEW.id_pregunta,NEW.id_pregunta,NULL,NULL);
    ELSIF NEW.id_respuesta IS NOT NULL THEN
        SELECT r.id_usuario,r.id_pregunta INTO destino,pregunta FROM public.respuestas r WHERE r.id=NEW.id_respuesta AND r.fecha_eliminacion IS NULL;
        IF pregunta IS NOT NULL THEN
            PERFORM public.foro_crear_notificacion(destino,NEW.id_usuario,'voto','respuesta',NEW.id_respuesta,pregunta,NEW.id_respuesta,NULL);
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.foro_notificar_seguidor() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
    PERFORM public.foro_crear_notificacion(NEW.id_seguido,NEW.id_seguidor,'seguidor','usuario',NEW.id_seguidor,NULL,NULL,NULL);
    RETURN NEW;
END;
$$;

-- Instalación reejecutable, sin quitar tablas ni datos existentes.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.preguntas'::regclass AND tgname='foro_aviso_pregunta' AND NOT tgisinternal) THEN
        CREATE TRIGGER foro_aviso_pregunta AFTER INSERT ON public.preguntas FOR EACH ROW EXECUTE FUNCTION public.foro_notificar_contenido();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.respuestas'::regclass AND tgname='foro_aviso_respuesta' AND NOT tgisinternal) THEN
        CREATE TRIGGER foro_aviso_respuesta AFTER INSERT ON public.respuestas FOR EACH ROW EXECUTE FUNCTION public.foro_notificar_contenido();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.comentarios'::regclass AND tgname='foro_aviso_comentario' AND NOT tgisinternal) THEN
        CREATE TRIGGER foro_aviso_comentario AFTER INSERT ON public.comentarios FOR EACH ROW EXECUTE FUNCTION public.foro_notificar_contenido();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.votos'::regclass AND tgname='foro_aviso_voto' AND NOT tgisinternal) THEN
        CREATE TRIGGER foro_aviso_voto AFTER INSERT OR UPDATE OF voto ON public.votos FOR EACH ROW EXECUTE FUNCTION public.foro_notificar_voto();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.seguimientos_usuarios'::regclass AND tgname='foro_aviso_seguidor' AND NOT tgisinternal) THEN
        CREATE TRIGGER foro_aviso_seguidor AFTER INSERT ON public.seguimientos_usuarios FOR EACH ROW EXECUTE FUNCTION public.foro_notificar_seguidor();
    END IF;
END $$;

-- Una sola regla de visibilidad para listado, contador y marcado de lectura.
CREATE OR REPLACE FUNCTION public.foro_notificaciones_visibles(uid BIGINT)
RETURNS SETOF public.notificaciones LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
    SELECT n.* FROM public.notificaciones n
    LEFT JOIN public.preguntas p ON p.id=n.id_pregunta
    LEFT JOIN public.respuestas r ON r.id=n.id_respuesta
    LEFT JOIN public.comentarios c ON c.id=n.id_comentario
    WHERE n.id_destinatario=uid AND NOT public.foro_hay_bloqueo(uid,n.id_actor)
      AND (n.id_pregunta IS NULL OR (p.id IS NOT NULL AND p.fecha_eliminacion IS NULL
          AND NOT public.foro_hay_bloqueo(uid,p.id_usuario)
          AND NOT EXISTS (SELECT 1 FROM public.preguntas_ocultas o WHERE o.id_usuario=uid AND o.id_pregunta=p.id)))
      AND (n.id_respuesta IS NULL OR (r.id IS NOT NULL AND r.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(uid,r.id_usuario)))
      AND (n.id_comentario IS NULL OR (c.id IS NOT NULL AND c.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(uid,c.id_usuario)))
      AND (n.tipo<>'voto' OR EXISTS (SELECT 1 FROM public.votos v WHERE v.id_usuario=n.id_actor AND v.voto=1
          AND ((n.objeto='pregunta' AND v.id_pregunta=n.id_objeto) OR (n.objeto='respuesta' AND v.id_respuesta=n.id_objeto))))
      AND (n.tipo<>'seguidor' OR EXISTS (SELECT 1 FROM public.seguimientos_usuarios s WHERE s.id_seguidor=n.id_actor AND s.id_seguido=uid));
$$;

REVOKE ALL ON FUNCTION public.foro_crear_notificacion(BIGINT,BIGINT,TEXT,TEXT,BIGINT,BIGINT,BIGINT,BIGINT),
 public.foro_notificar_menciones(TEXT,BIGINT,TEXT,BIGINT,BIGINT,BIGINT,BIGINT),
 public.foro_notificar_contenido(), public.foro_notificar_voto(), public.foro_notificar_seguidor(),
 public.foro_notificaciones_visibles(BIGINT) FROM PUBLIC, anon, authenticated;
COMMIT;
