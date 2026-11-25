"""Pruebas sin red de validación y pruebas HTTP con cursor simulado."""
import ast
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parents[1]
# Ejecuta las funciones puras desde el archivo real, aun sin Flask/psycopg2.
modulo = ast.parse((BACKEND / 'routes/usuarios.py').read_text(encoding='utf-8'))
ns = {'urlsplit': urlsplit}
exec(compile(ast.Module(body=[n for n in modulo.body if isinstance(n, ast.FunctionDef) and n.name in ('_datos_perfil', '_insignias')], type_ignores=[]), str(BACKEND / 'routes/usuarios.py'), 'exec'), ns)

class Validacion(unittest.TestCase):
    def test_bio(self):
        self.assertEqual(ns['_datos_perfil']({'biografia':'  Hola  '}), {'biografia':'Hola'})
    def test_bio_limite(self):
        for bio in (True, None, 'a'*501, 'a\x00'):
            with self.subTest(bio=bio), self.assertRaises(ValueError): ns['_datos_perfil']({'biografia':bio})
    def test_avatar_https(self):
        self.assertEqual(ns['_datos_perfil']({'avatar_url':'https://example.org/foto.png'}),{'avatar_url':'https://example.org/foto.png'})
    def test_quitar_avatar(self):
        self.assertEqual(ns['_datos_perfil']({'avatar_url':''}),{'avatar_url':None})
    def test_avatar_invalido(self):
        for url in ('http://example.org','javascript:alert(1)','https://','https://a:b@example.org','https://example.org:99999/a','https://a\\b','https://a b','data:image/png,x',None):
            with self.subTest(url=url), self.assertRaises(ValueError): ns['_datos_perfil']({'avatar_url':url})
    def test_no_editar_rol(self):
        for datos in ({'rol':'admin'}, {'biografia':'hola','id':2}, {}, [], {'correo':'a@b.c'}):
            with self.subTest(datos=datos), self.assertRaises(ValueError): ns['_datos_perfil'](datos)
    def test_insignias_sin_actividad(self):
        self.assertEqual(ns['_insignias'](0,0,-1),[])
    def test_insignias_reales(self):
        self.assertEqual(len(ns['_insignias'](10,5,25)),5)
        self.assertEqual(ns['_insignias'](1,0,24),['Primera publicación'])

try:
    import flask
    import psycopg2
    import jwt
except ImportError:
    DEPENDENCIAS = False
else:
    DEPENDENCIAS = True
    sys.path.insert(0,str(BACKEND))
    os.environ['DATABASE_URL']='postgresql://test:test@127.0.0.1:1/test'
    os.environ['JWT_SECRET']='clave-de-pruebas-locales-no-productiva'
    from config import Config
    from extensions import ConexionPostgres
    from app_usuarios import app as usuarios
    from app_preguntas import app as foro

@unittest.skipUnless(DEPENDENCIAS, 'Faltan dependencias del backend')
class HTTP(unittest.TestCase):
    def setUp(self):
        self.con=MagicMock(); self.cur=self.con.cursor.return_value
        self.cur.__enter__.return_value=self.cur
        parche=patch.object(ConexionPostgres,'connection',new=property(lambda _:self.con))
        parche.start(); self.addCleanup(parche.stop)
        self.identidad=dict(id=7,correo='privado@example.org',rol='estudiante')
        self.headers={'Authorization':'Bearer '+jwt.encode({'id':7,'exp':int(time.time())+600},Config.JWT_SECRET,algorithm='HS256')}
    def test_editar_sin_sesion(self):
        self.assertEqual(usuarios.test_client().put('/usuarios/perfil',json={'biografia':'hola'}).status_code,401)
    def test_no_autoseguimiento(self):
        self.cur.fetchone.return_value=self.identidad
        r=usuarios.test_client().put('/usuarios/7/seguir',json={'seguir':True},headers=self.headers)
        self.assertEqual(r.status_code,400); self.con.commit.assert_not_called()
    def test_seguir_usuario_idempotente(self):
        self.cur.fetchone.side_effect=[self.identidad,{'id':8},{'bloqueo':False}]
        r=usuarios.test_client().put('/usuarios/8/seguir',json={'seguir':True},headers=self.headers)
        self.assertEqual(r.status_code,200); self.assertIn('ON CONFLICT DO NOTHING',self.cur.execute.call_args.args[0]); self.assertEqual(self.cur.execute.call_args.args[1],(7,8))
    def test_dejar_comunidad(self):
        self.cur.fetchone.side_effect=[self.identidad,{'id':1}]
        r=foro.test_client().put('/categorias/1/seguir',json={'seguir':False},headers=self.headers)
        self.assertEqual(r.status_code,200); self.assertEqual(self.cur.execute.call_args.args[1],(7,1))
    def test_perfil_sin_datos_privados(self):
        self.cur.fetchone.return_value=dict(id=8,nombre_apellido='Usuario',rol='estudiante',fecha_registro='2026-01-01',biografia='',avatar_url=None,karma=1,publicaciones=1,respuestas=0,soluciones=0,seguidores=0,seguidos=0,comunidades=0,siguiendo=False)
        r=usuarios.test_client().get('/usuarios/8/perfil')
        self.assertEqual(r.status_code,200); self.assertNotIn('correo',r.json); self.assertNotIn('password_hash',r.json); self.assertIn('Primera publicación',r.json['insignias'])
    def test_feed_seguido_sin_sesion(self):
        self.assertEqual(foro.test_client().get('/preguntas?seguidas=1').status_code,401)
    def test_actividad_offset_invalido(self):
        self.assertEqual(usuarios.test_client().get('/usuarios/8/actividad?offset=-1').status_code,400)

if __name__ == '__main__': unittest.main()
