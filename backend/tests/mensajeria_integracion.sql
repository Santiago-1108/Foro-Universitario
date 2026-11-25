-- SOLO base de pruebas con migraciones 001 a 007. Revierte datos al final.
BEGIN;
DO $$
DECLARE a BIGINT; b BIGINT; c BIGINT; cid BIGINT; mid BIGINT; marca TEXT := md5(random()::text || clock_timestamp()::text);
BEGIN
 INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba A','a-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO a;
 INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba B','b-'||marca||'@example.invalid','no-login','docente') RETURNING id INTO b;
 INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba C','c-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO c;
 INSERT INTO public.conversaciones(usuario_a,usuario_b) VALUES(LEAST(a,b),GREATEST(a,b)) RETURNING id INTO cid;
 BEGIN
  INSERT INTO public.conversaciones(usuario_a,usuario_b) VALUES(LEAST(a,b),GREATEST(a,b));
  RAISE EXCEPTION 'Falta restricción de conversación única';
 EXCEPTION WHEN unique_violation THEN NULL; END;
 BEGIN
  INSERT INTO public.mensajes(id_conversacion,id_emisor,contenido) VALUES(cid,c,'intruso');
  RAISE EXCEPTION 'Se permitió un emisor ajeno';
 EXCEPTION WHEN check_violation THEN NULL; END;
 INSERT INTO public.mensajes(id_conversacion,id_emisor,contenido) VALUES(cid,a,'Mensaje privado') RETURNING id INTO mid;
 IF NOT EXISTS(SELECT 1 FROM public.mensajes WHERE id=mid AND fecha_lectura IS NULL) THEN RAISE EXCEPTION 'Mensaje no registrado'; END IF;
 UPDATE public.mensajes SET fecha_lectura=now() WHERE id=mid;
 IF NOT EXISTS(SELECT 1 FROM public.mensajes WHERE id=mid AND fecha_lectura IS NOT NULL) THEN RAISE EXCEPTION 'Lectura no registrada'; END IF;
 IF has_table_privilege('anon','public.mensajes','SELECT') OR has_table_privilege('authenticated','public.mensajes','SELECT') THEN RAISE EXCEPTION 'Permisos directos excesivos'; END IF;
 RAISE NOTICE 'Restricciones y persistencia verificadas';
END $$;
ROLLBACK;
