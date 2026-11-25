-- SOLO para una base nueva y vacía. No ejecutar sobre un foro existente.
-- No crea cuentas de ejemplo ni contraseñas conocidas.

BEGIN;

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

INSERT INTO categorias (nombre, descripcion) VALUES
('Programación Web', 'Temas de Flask, APIs REST y desarrollo web'),
('Bases de Datos', 'SQL, diseño de esquemas y consultas'),
('Redes', 'Protocolos, modelo OSI y comunicación en red');

COMMIT;
