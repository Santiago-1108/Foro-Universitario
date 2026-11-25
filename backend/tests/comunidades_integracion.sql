-- SOLO en BD de pruebas tras 010/011. Todo se revierte, incluso si falla una aserción.
BEGIN;
DO $$
DECLARE a BIGINT; b BIGINT; cat BIGINT; cid BIGINT; pid BIGINT; rid BIGINT; suf TEXT:=gen_random_uuid()::text;
BEGIN
 INSERT INTO usuarios(nombre_apellido,correo,password_hash,rol) VALUES('Prueba propietaria',suf||'@prueba.invalid','no-es-password','estudiante') RETURNING id INTO a;
 INSERT INTO usuarios(nombre_apellido,correo,password_hash,rol) VALUES('Prueba visitante','b'||suf||'@prueba.invalid','no-es-password','estudiante') RETURNING id INTO b;
 INSERT INTO categorias(nombre,descripcion) VALUES('Prueba '||suf,'Rollback') RETURNING id INTO cat;
 INSERT INTO comunidades(id_categoria,id_propietario,nombre,slug,descripcion,tipo) VALUES(cat,a,'Prueba '||suf,suf,'Rollback','restringida') RETURNING id INTO cid;
 INSERT INTO miembros_comunidades(id_comunidad,id_usuario,rol,aprobado) VALUES(cid,a,'propietario',true),(cid,b,'miembro',false);
 INSERT INTO preguntas(id_usuario,id_categoria,id_comunidad,titulo,contenido) VALUES(a,cat,cid,'Prueba','Texto') RETURNING id INTO pid;
 INSERT INTO respuestas(id_usuario,id_pregunta,contenido) VALUES(a,pid,'Respuesta') RETURNING id INTO rid;
 BEGIN INSERT INTO preguntas(id_usuario,id_categoria,id_comunidad,titulo,contenido) VALUES(b,cat,cid,'No autorizada','Texto'); RAISE EXCEPTION 'Falló la restricción de publicaciones'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN INSERT INTO respuestas(id_usuario,id_pregunta,contenido) VALUES(b,pid,'No autorizada'); RAISE EXCEPTION 'Falló la restricción de respuestas'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN INSERT INTO comentarios(id_usuario,id_respuesta,contenido) VALUES(b,rid,'No autorizado'); RAISE EXCEPTION 'Falló la restricción de comentarios'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 UPDATE miembros_comunidades SET aprobado=true WHERE id_comunidad=cid AND id_usuario=b;
 INSERT INTO respuestas(id_usuario,id_pregunta,contenido) VALUES(b,pid,'Autorizada');
 INSERT INTO comentarios(id_usuario,id_respuesta,contenido) VALUES(b,rid,'Autorizado');
 RAISE NOTICE 'Comunidades restringidas: verificación correcta';
END $$;
ROLLBACK;
