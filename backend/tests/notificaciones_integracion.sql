-- PRUEBA MANUAL: solo base de pruebas con migraciones 001 a 005 aplicadas.
-- Crea datos temporales en una transacción y revierte todo; las secuencias pueden avanzar.
BEGIN;
DO $$
DECLARE a BIGINT; b BIGINT; c BIGINT; cat BIGINT; p BIGINT; r BIGINT; co BIGINT;
        marca TEXT := md5(random()::text || clock_timestamp()::text);
BEGIN
    INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba A','a-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO a;
    INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba B','b-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO b;
    INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba C','c-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO c;
    INSERT INTO public.categorias(nombre,descripcion) VALUES ('Prueba-'||marca,'Solo prueba') RETURNING id INTO cat;
    INSERT INTO public.preguntas(id_usuario,id_categoria,titulo,contenido) VALUES(a,cat,'Pregunta', 'Hola @'||b||' @'||b||' @'||a||' @9223372036854775808') RETURNING id INTO p;
    IF (SELECT count(*) FROM public.foro_notificaciones_visibles(b) WHERE tipo='mencion')<>1 THEN RAISE EXCEPTION 'Mención repetida o ausente'; END IF;
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(a)) THEN RAISE EXCEPTION 'Autonotificación'; END IF;
    INSERT INTO public.respuestas(id_usuario,id_pregunta,contenido) VALUES(b,p,'Respuesta a la pregunta') RETURNING id INTO r;
    IF (SELECT count(*) FROM public.foro_notificaciones_visibles(a) WHERE tipo='respuesta')<>1 THEN RAISE EXCEPTION 'Respuesta sin aviso'; END IF;
    INSERT INTO public.comentarios(id_usuario,id_respuesta,contenido) VALUES(c,r,'Comentario') RETURNING id INTO co;
    INSERT INTO public.comentarios(id_usuario,id_respuesta,id_comentario_padre,contenido) VALUES(a,r,co,'Respuesta al comentario');
    IF (SELECT count(*) FROM public.foro_notificaciones_visibles(b) WHERE tipo='comentario')<>1 OR (SELECT count(*) FROM public.foro_notificaciones_visibles(c) WHERE tipo='comentario')<>1 THEN RAISE EXCEPTION 'Destinatario de comentario incorrecto'; END IF;
    INSERT INTO public.votos(id_usuario,id_pregunta,voto) VALUES(b,p,-1);
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(a) WHERE tipo='voto') THEN RAISE EXCEPTION 'Voto negativo notificado'; END IF;
    UPDATE public.votos SET voto=1 WHERE id_usuario=b AND id_pregunta=p;
    UPDATE public.votos SET voto=1 WHERE id_usuario=b AND id_pregunta=p;
    IF (SELECT count(*) FROM public.foro_notificaciones_visibles(a) WHERE tipo='voto')<>1 THEN RAISE EXCEPTION 'Voto duplicado o ausente'; END IF;
    UPDATE public.votos SET voto=-1 WHERE id_usuario=b AND id_pregunta=p;
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(a) WHERE tipo='voto') THEN RAISE EXCEPTION 'Voto retirado visible'; END IF;
    INSERT INTO public.seguimientos_usuarios(id_seguidor,id_seguido) VALUES(b,a) ON CONFLICT DO NOTHING;
    INSERT INTO public.seguimientos_usuarios(id_seguidor,id_seguido) VALUES(b,a) ON CONFLICT DO NOTHING;
    IF (SELECT count(*) FROM public.foro_notificaciones_visibles(a) WHERE tipo='seguidor')<>1 THEN RAISE EXCEPTION 'Seguimiento duplicado o ausente'; END IF;
    UPDATE public.notificaciones SET fecha_lectura=now() WHERE id_destinatario=a AND tipo='seguidor';
    IF NOT EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(a) WHERE tipo='seguidor' AND fecha_lectura IS NOT NULL) THEN RAISE EXCEPTION 'Lectura no persistida'; END IF;
    INSERT INTO public.bloqueos_usuarios(id_usuario,id_bloqueado) VALUES(a,b);
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(a) WHERE id_actor=b) THEN RAISE EXCEPTION 'Bloqueo no respetado'; END IF;
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(b) WHERE id_actor=a OR id_pregunta=p) THEN RAISE EXCEPTION 'Bloqueo de autor no respetado'; END IF;
    INSERT INTO public.preguntas_ocultas(id_usuario,id_pregunta) VALUES(c,p);
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(c) WHERE id_pregunta=p) THEN RAISE EXCEPTION 'Publicación oculta visible'; END IF;
    UPDATE public.preguntas SET fecha_eliminacion=now() WHERE id=p;
    IF EXISTS(SELECT 1 FROM public.foro_notificaciones_visibles(a) WHERE id_pregunta=p) THEN RAISE EXCEPTION 'Publicación eliminada visible'; END IF;
    RAISE NOTICE 'Pruebas de notificaciones superadas';
END $$;
ROLLBACK;
