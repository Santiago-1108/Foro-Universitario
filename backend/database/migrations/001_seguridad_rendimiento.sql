-- Migración incremental: no elimina ni modifica filas existentes.
-- Ejecutar primero en una copia de pruebas. Si hay datos inválidos,
-- la transacción aborta; no se corrigen ni eliminan automáticamente.
BEGIN;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.votos WHERE voto NOT IN (-1, 1)
       OR (id_pregunta IS NULL) = (id_respuesta IS NULL)) THEN
    RAISE EXCEPTION 'Existen votos inválidos; revisar manualmente antes de migrar';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.votos'::regclass AND conname = 'votos_signo_valido') THEN
    ALTER TABLE public.votos ADD CONSTRAINT votos_signo_valido CHECK (voto IN (-1, 1));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.votos'::regclass AND conname = 'votos_destino_unico') THEN
    ALTER TABLE public.votos ADD CONSTRAINT votos_destino_unico CHECK ((id_pregunta IS NULL) <> (id_respuesta IS NULL));
  END IF;
END $$;
-- El esquema original ya tiene UNIQUE (id_usuario, id_pregunta) y UNIQUE
-- (id_usuario, id_respuesta). Se asegura su presencia si faltan en la instalación.
CREATE UNIQUE INDEX IF NOT EXISTS unique_voto_pregunta ON public.votos (id_usuario, id_pregunta);
CREATE UNIQUE INDEX IF NOT EXISTS unique_voto_respuesta ON public.votos (id_usuario, id_respuesta);
CREATE INDEX IF NOT EXISTS ix_votos_pregunta ON public.votos (id_pregunta);
CREATE INDEX IF NOT EXISTS ix_votos_respuesta ON public.votos (id_respuesta);
CREATE INDEX IF NOT EXISTS ix_respuestas_pregunta ON public.respuestas (id_pregunta);
CREATE INDEX IF NOT EXISTS ix_comentarios_respuesta ON public.comentarios (id_respuesta);
CREATE INDEX IF NOT EXISTS ix_preguntas_fecha ON public.preguntas (fecha_creacion DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_preguntas_categoria_fecha ON public.preguntas (id_categoria, fecha_creacion DESC, id DESC);
COMMIT;
