-- SOLO en base de pruebas con migraciones 001 a 006. Transacción revertida al final.
BEGIN;
DO $$
DECLARE a BIGINT; b BIGINT; m BIGINT; cat BIGINT; p BIGINT; t BIGINT;
        marca TEXT := md5(random()::text || clock_timestamp()::text);
BEGIN
 INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba A','a-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO a;
 INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba B','b-'||marca||'@example.invalid','no-login','estudiante') RETURNING id INTO b;
 INSERT INTO public.usuarios(nombre_apellido,correo,password_hash,rol) VALUES ('Prueba Admin','m-'||marca||'@example.invalid','no-login','admin') RETURNING id INTO m;
 INSERT INTO public.categorias(nombre,descripcion) VALUES ('Prueba-'||marca,'Solo prueba') RETURNING id INTO cat;
 INSERT INTO public.preguntas(id_usuario,id_categoria,titulo,contenido) VALUES(b,cat,'Pregunta','Contenido') RETURNING id INTO p;
 INSERT INTO public.reportes(id_reportante,tipo,id_objeto,motivo) VALUES(a,'pregunta',p,'spam') RETURNING id INTO t;
 BEGIN
  INSERT INTO public.reportes(id_reportante,tipo,id_objeto,motivo) VALUES(a,'pregunta',p,'spam');
  RAISE EXCEPTION 'Falta restricción de reporte pendiente único';
 EXCEPTION WHEN unique_violation THEN NULL; END;
 UPDATE public.reportes SET estado='atendido',id_moderador=m,fecha_revision=now() WHERE id=t;
 INSERT INTO public.historial_moderacion(id_admin,accion,tipo,id_objeto) VALUES(m,'atendido_reporte','reporte',t);
 UPDATE public.usuarios SET suspendido=true,version_sesion=version_sesion+1 WHERE id=b;
 UPDATE public.usuarios SET suspendido=false,version_sesion=version_sesion+1 WHERE id=b;
 IF (SELECT version_sesion FROM public.usuarios WHERE id=b)<>2 THEN RAISE EXCEPTION 'Versión de sesión incorrecta'; END IF;
 BEGIN
  UPDATE public.usuarios SET suspendido=true WHERE id=m;
  RAISE EXCEPTION 'Falta restricción contra suspender administradores';
 EXCEPTION WHEN check_violation THEN NULL; END;
 UPDATE public.preguntas SET fijada=true,cerrada=true WHERE id=p;
 IF NOT EXISTS(SELECT 1 FROM public.preguntas WHERE id=p AND fijada AND cerrada) THEN RAISE EXCEPTION 'Estado de publicación no persistido'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.historial_moderacion WHERE id_admin=m AND id_objeto=t AND tipo='reporte') THEN RAISE EXCEPTION 'Historial no registrado'; END IF;
 RAISE NOTICE 'Verificaciones de restricciones y persistencia superadas';
END $$;
ROLLBACK;
