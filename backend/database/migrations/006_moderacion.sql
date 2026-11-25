-- Ejecutar después de 001-005. No elimina datos. Probar antes de producción.
BEGIN;
ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS suspendido BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS version_sesion BIGINT NOT NULL DEFAULT 0;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.usuarios'::regclass AND conname='usuarios_admin_no_suspendido') THEN
  ALTER TABLE public.usuarios ADD CONSTRAINT usuarios_admin_no_suspendido CHECK (NOT suspendido OR rol<>'admin');
 END IF;
END $$;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS fijada BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE public.preguntas ADD COLUMN IF NOT EXISTS cerrada BOOLEAN NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS public.reportes (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_reportante BIGINT NOT NULL REFERENCES public.usuarios(id),
 tipo VARCHAR(15) NOT NULL CHECK(tipo IN ('pregunta','respuesta','comentario','usuario')),
 id_objeto BIGINT NOT NULL CHECK(id_objeto>0),
 motivo VARCHAR(30) NOT NULL CHECK(motivo IN ('spam','acoso','contenido_inapropiado','otro')),
 detalle VARCHAR(500) NOT NULL DEFAULT '',
 estado VARCHAR(15) NOT NULL DEFAULT 'pendiente' CHECK(estado IN ('pendiente','atendido','descartado')),
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
 id_moderador BIGINT REFERENCES public.usuarios(id),
 fecha_revision TIMESTAMPTZ,
 nota_revision VARCHAR(500),
 CHECK ((estado='pendiente' AND id_moderador IS NULL AND fecha_revision IS NULL) OR (estado<>'pendiente' AND id_moderador IS NOT NULL AND fecha_revision IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_reportes_pendientes ON public.reportes(id_reportante,tipo,id_objeto) WHERE estado='pendiente';
CREATE INDEX IF NOT EXISTS ix_reportes_estado ON public.reportes(estado,id DESC);
CREATE TABLE IF NOT EXISTS public.historial_moderacion (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_admin BIGINT NOT NULL REFERENCES public.usuarios(id),
 accion VARCHAR(40) NOT NULL,
 tipo VARCHAR(15) NOT NULL,
 id_objeto BIGINT NOT NULL,
 detalle VARCHAR(500) NOT NULL DEFAULT '',
 fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.reportes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historial_moderacion ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS ix_preguntas_fijadas ON public.preguntas(fecha_creacion DESC,id DESC) WHERE fijada AND fecha_eliminacion IS NULL;
COMMIT;
