-- Script para PostgreSQL (Supabase). Pégalo completo en SQL Editor → New query → Run.
-- Borra y vuelve a crear las tablas del foro, así que sirve también para volver a los datos de ejemplo.
-- En Supabase la base de datos ya existe: no hay CREATE DATABASE ni USE.
--
-- Contraseñas en texto plano (hash pbkdf2:sha256 de werkzeug):
-- ana.admin@universidad.edu       -> admin123
-- carlos.docente@universidad.edu  -> docente123
-- luis.est@universidad.edu        -> est123
-- maria.est@universidad.edu       -> est456
-- pedro.est@universidad.edu       -> est789

DROP TABLE IF EXISTS votos, comentarios, respuestas, preguntas, categorias, usuarios CASCADE;

CREATE TABLE public.usuarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_apellido VARCHAR(120) NOT NULL,
    correo VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('estudiante', 'docente', 'admin')),
    fecha_registro TIMESTAMPTZ(0) NOT NULL DEFAULT now()
);

CREATE TABLE public.categorias (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL,
    descripcion TEXT
);

CREATE TABLE public.preguntas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
    id_categoria BIGINT NOT NULL REFERENCES public.categorias(id),
    titulo VARCHAR(200) NOT NULL,
    contenido TEXT NOT NULL,
    fecha_creacion TIMESTAMPTZ(0) NOT NULL DEFAULT now()
);

CREATE TABLE public.respuestas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
    id_pregunta BIGINT NOT NULL REFERENCES public.preguntas(id),
    contenido TEXT NOT NULL,
    fecha_creacion TIMESTAMPTZ(0) NOT NULL DEFAULT now()
);

CREATE TABLE public.comentarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
    id_respuesta BIGINT NOT NULL REFERENCES public.respuestas(id),
    contenido TEXT NOT NULL,
    fecha_creacion TIMESTAMPTZ(0) NOT NULL DEFAULT now()
);

CREATE TABLE public.votos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT NOT NULL REFERENCES public.usuarios(id),
    id_pregunta BIGINT NULL REFERENCES public.preguntas(id),
    id_respuesta BIGINT NULL REFERENCES public.respuestas(id),
    voto SMALLINT NOT NULL,
    CONSTRAINT unique_voto_pregunta UNIQUE (id_usuario, id_pregunta),
    CONSTRAINT unique_voto_respuesta UNIQUE (id_usuario, id_respuesta)
);

-- Seguridad a nivel de fila (RLS), como en la guía de despliegue.
-- Sin políticas, la clave pública (anon) de Supabase NO puede leer ni escribir estas tablas.
-- El backend entra con el usuario postgres de la cadena de conexión, que no está sujeto a RLS.
ALTER TABLE public.usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.preguntas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.respuestas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comentarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.votos ENABLE ROW LEVEL SECURITY;

INSERT INTO usuarios (nombre_apellido, correo, password_hash, rol) VALUES
('Ana Admin', 'ana.admin@universidad.edu', 'pbkdf2:sha256:600000$eqOGrrsm8MnIWPSO$941a71fa53dc13781708201cfa82c050797d9aaa5ca079c97727297019273407', 'admin'),
('Carlos Docente', 'carlos.docente@universidad.edu', 'pbkdf2:sha256:600000$IvdOFrURybx6qubg$128262e59faee9dfb919bccebaab2d53ec6052b4eee0c20006d5dd7a6027d8b2', 'docente'),
('Luis Estudiante', 'luis.est@universidad.edu', 'pbkdf2:sha256:600000$AEfp25T0NpvKw6Ti$dbc5d10a2e87bf8078d4bc7d77b1869def8d9ad4ee834c89a69ccf05f62608ff', 'estudiante'),
('Maria Estudiante', 'maria.est@universidad.edu', 'pbkdf2:sha256:600000$e7CWSJNRzuFiyZWq$641e61ca49faf4981baf7ebe02c8d791bde7a01c95e3e4ace452a355f5d15ea8', 'estudiante'),
('Pedro Estudiante', 'pedro.est@universidad.edu', 'pbkdf2:sha256:600000$Baj9sKEl4o4kEodn$13c2094f815c697c17a656a612a81f3342878a7f2dc7f8e256512a03e4863963', 'estudiante');

INSERT INTO categorias (nombre, descripcion) VALUES
('Programación Web', 'Temas de Flask, APIs REST y desarrollo web'),
('Bases de Datos', 'SQL, diseño de esquemas y consultas'),
('Redes', 'Protocolos, modelo OSI y comunicación en red');

INSERT INTO preguntas (id_usuario, id_categoria, titulo, contenido) VALUES
(3, 1, '¿Cómo conectar Flask con MySQL?', 'Necesito conectar mi servicio Flask a MySQL usando Flask-MySQLdb. ¿Qué debo configurar?'),
(4, 2, 'Diferencia entre INNER JOIN y LEFT JOIN', 'No tengo clara la diferencia práctica entre INNER JOIN y LEFT JOIN. ¿Alguien puede explicarlo?'),
(5, 1, '¿Qué es un JWT y para qué sirve?', 'Vi que se usa JWT para autenticar APIs. ¿Cómo funciona a grandes rasgos?'),
(3, 3, '¿Cómo funciona el modelo OSI?', 'Quiero un resumen de las capas del modelo OSI aplicado a servicios web.'),
(4, 2, 'Normalización hasta 3FN', '¿Qué busca la tercera forma normal y cómo se aplica en un foro como este?');

INSERT INTO respuestas (id_usuario, id_pregunta, contenido) VALUES
(2, 1, 'En config.py defines MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD y MYSQL_DB, y luego usas Flask-MySQLdb para obtener el cursor.'),
(1, 1, 'Además revisa que el usuario de MySQL tenga permisos sobre foro_db y que el servicio esté en el puerto correcto.'),
(2, 2, 'INNER JOIN solo devuelve filas con coincidencia en ambas tablas. LEFT JOIN conserva todas las filas de la tabla izquierda.'),
(5, 2, 'Un ejemplo: listar preguntas con su categoría. Si una categoría no tiene preguntas, LEFT JOIN desde categorias las muestra igual.'),
(2, 3, 'JWT es un token firmado con un secreto. El cliente lo envía en Authorization y el servidor verifica la firma sin consultar la sesión.'),
(2, 4, 'El modelo OSI tiene 7 capas. En la práctica HTTP opera en aplicación, TCP en transporte e IP en red.'),
(2, 5, '3FN evita que un atributo no clave dependa de otro atributo no clave. En el foro, el rol va en usuarios, no se repite en cada pregunta.'),
(3, 5, 'También ayuda a no duplicar el nombre de la categoría dentro de cada pregunta: se referencia por id_categoria.');

INSERT INTO comentarios (id_usuario, id_respuesta, contenido) VALUES
(4, 1, 'Gracias, con eso ya pude conectar el servicio de usuarios.'),
(3, 1, '¿El cursor se cierra después de cada consulta o se reutiliza?'),
(3, 3, 'Quedó claro con el ejemplo de las categorías.'),
(4, 5, 'Entonces el JWT_SECRET debe ser el mismo en los tres microservicios.'),
(5, 6, 'Muy útil el resumen de capas, gracias profesor.'),
(4, 7, 'Voy a revisar mis tablas para no repetir datos de usuario.');

INSERT INTO votos (id_usuario, id_pregunta, id_respuesta, voto) VALUES
(3, 1, NULL, 1),
(4, 1, NULL, 1),
(5, 2, NULL, 1),
(3, 3, NULL, 1),
(2, 5, NULL, 1),
(4, NULL, 1, 1),
(5, NULL, 1, 1),
(3, NULL, 3, 1),
(1, NULL, 5, 1),
(5, NULL, 7, -1);
