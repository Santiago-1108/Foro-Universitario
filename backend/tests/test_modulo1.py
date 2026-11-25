"""Pruebas HTTP unitarias con conexión simulada; no contactan Supabase."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Valores exclusivos de pruebas; no se modifica ningún archivo de configuración.
os.environ['DATABASE_URL'] = 'postgresql://test:test@127.0.0.1:1/test'
os.environ['JWT_SECRET'] = 'clave-de-pruebas-locales-no-productiva'
try:
    import flask, psycopg2, jwt
except ImportError as e:
    raise unittest.SkipTest('Faltan dependencias del backend') from e
from app_usuarios import app as usuarios_app
from app_preguntas import app as foro_app
from app_interacciones import app as interacciones_app
from config import Config
from extensions import ConexionPostgres


class Modulo1(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        self.cursor.__enter__.return_value = self.cursor
        self.connection_patch = patch.object(ConexionPostgres, 'connection', new=property(lambda _: self.connection))
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)

    def headers(self, rol='admin', exp=True):
        payload = {'id': 7, 'rol': rol}
        if exp:
            payload['exp'] = int(time.time()) + 600
        return {'Authorization': 'Bearer ' + jwt.encode(payload, Config.JWT_SECRET, algorithm='HS256')}

    def test_rol_actual_prevalece(self):
        self.cursor.fetchone.return_value = {'id': 7, 'correo': 'test@example.org', 'rol': 'estudiante'}
        r = usuarios_app.test_client().get('/usuarios', headers=self.headers())
        self.assertEqual(r.status_code, 403)

    def test_usuario_eliminado(self):
        self.cursor.fetchone.return_value = None
        r = usuarios_app.test_client().get('/usuarios/7', headers=self.headers())
        self.assertEqual(r.status_code, 401)

    def test_token_sin_expiracion(self):
        r = usuarios_app.test_client().get('/usuarios', headers=self.headers(exp=False))
        self.assertEqual(r.status_code, 401)
        self.cursor.execute.assert_not_called()

    def test_json_no_objeto(self):
        r = usuarios_app.test_client().post('/auth/registro', json=['incorrecto'])
        self.assertEqual(r.status_code, 400)

    def test_identificador_booleano(self):
        r = foro_app.test_client().post('/preguntas', json={'id_categoria': True})
        self.assertEqual(r.status_code, 400)

    def test_paginacion_invalida(self):
        r = foro_app.test_client().get('/preguntas?limite=1000')
        self.assertEqual(r.status_code, 400)
        self.cursor.execute.assert_not_called()

    def test_paginacion_y_conteos(self):
        self.cursor.fetchall.return_value = [dict(id=1, id_usuario=7, id_categoria=1, titulo='Título', contenido='Texto', fecha_creacion='2026-11-24', nombre_autor='Test', nombre_categoria='Redes', total_votos=3, cantidad_respuestas=2)]
        r = foro_app.test_client().get('/preguntas/categoria/1?limite=21&offset=20')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json[0]['total_votos'], 3)
        self.assertEqual(r.json[0]['cantidad_respuestas'], 2)
        self.assertEqual(self.cursor.execute.call_args.args[1], (1, 21, 20))

    def test_voto_negativo_upsert(self):
        self.cursor.fetchone.side_effect = [dict(id=7, correo='test@example.org', rol='estudiante'), {'id': 3}, dict(id=9, id_usuario=7, id_pregunta=3, id_respuesta=None, voto=-1), dict(total_votos=-1, cantidad=1)]
        r = interacciones_app.test_client().post('/votos', json={'id_pregunta': 3, 'voto': -1}, headers=self.headers())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['voto'], -1)
        self.assertTrue(any('ON CONFLICT' in c.args[0] for c in self.cursor.execute.call_args_list))
        self.connection.commit.assert_called_once()

    def test_cancelacion(self):
        self.cursor.fetchone.side_effect = [dict(id=7, correo='test@example.org', rol='estudiante'), {'id': 3}, dict(total_votos=0, cantidad=0)]
        r = interacciones_app.test_client().post('/votos', json={'id_respuesta': 3, 'voto': 0}, headers=self.headers())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['voto'], 0)
        self.assertTrue(any('DELETE FROM votos' in c.args[0] for c in self.cursor.execute.call_args_list))

    def test_voto_booleano(self):
        self.cursor.fetchone.return_value = dict(id=7, correo='test@example.org', rol='estudiante')
        r = interacciones_app.test_client().post('/votos', json={'id_pregunta': 3, 'voto': True}, headers=self.headers())
        self.assertEqual(r.status_code, 400)
        self.connection.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
