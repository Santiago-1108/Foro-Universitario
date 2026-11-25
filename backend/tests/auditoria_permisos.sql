-- Solo lectura. Ejecutar en Supabase de pruebas tras 008.
SELECT schemaname, tablename, rowsecurity
FROM pg_tables WHERE schemaname='public'
AND tablename IN ('usuarios','categorias','preguntas','respuestas','comentarios','votos','votos_encuesta','borradores','seguimientos_usuarios','seguimientos_categorias','preguntas_guardadas','preguntas_ocultas','bloqueos_usuarios','notificaciones','reportes','historial_moderacion','conversaciones','mensajes')
ORDER BY tablename;
-- Debe devolver 0 filas para anon/authenticated en las tablas del foro.
SELECT grantee,table_name,privilege_type FROM information_schema.table_privileges
WHERE table_schema='public' AND grantee IN ('PUBLIC','anon','authenticated')
AND table_name IN ('usuarios','categorias','preguntas','respuestas','comentarios','votos','votos_encuesta','borradores','seguimientos_usuarios','seguimientos_categorias','preguntas_guardadas','preguntas_ocultas','bloqueos_usuarios','notificaciones','reportes','historial_moderacion','conversaciones','mensajes');
