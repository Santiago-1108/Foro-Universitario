"""Pruebas unitarias de validación y endpoints (con PostgreSQL simulado)."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'postgresql://test:test@127.0.0.1:1/test'
os.environ['JWT_SECRET'] = 'clave-de-pruebas-locales-no-productiva'
import ast
from urllib.parse import urlsplit
ruta = Path(__file__).resolve().parents[1] / 'routes/preguntas.py'
nodos = [n for n in ast.parse(ruta.read_text()).body if
         (isinstance(n, ast.FunctionDef) and n.name == '_datos_publicacion') or
         (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ETIQUETAS' for t in n.targets))]
ns = {'urlsplit': urlsplit}
exec(compile(ast.Module(body=nodos, type_ignores=[]), str(ruta), 'exec'), ns)
_datos_publicacion = ns['_datos_publicacion']
try:
    import flask, psycopg2, jwt
except ImportError:
    DEPENDENCIAS = False
else:
    DEPENDENCIAS = True
    from config import Config
    from extensions import ConexionPostgres
    from app_preguntas import app as foro
    from app_interacciones import app as interacciones

BASE = dict(id_categoria=1, titulo='Pregunta', contenido='Contenido')

class Validacion(unittest.TestCase):
    def test_texto(self):
        self.assertEqual(_datos_publicacion(BASE)['tipo'], 'texto')
    def test_url_https(self):
        self.assertEqual(_datos_publicacion(dict(BASE,tipo='imagen',recurso_url='https://example.org/a.png'))['recurso_url'],'https://example.org/a.png')
    def test_url_insegura(self):
        for url in ('javascript:alert(1)', 'http://example.org', 'https://a:b@example.org', 'https://', 'https://a\\b'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _datos_publicacion(dict(BASE,tipo='enlace',recurso_url=url))
    def test_encuesta_valida(self):
        self.assertEqual(_datos_publicacion(dict(BASE,tipo='encuesta',opciones_encuesta=['A','B']))['opciones_encuesta'],['A','B'])
    def test_encuesta_invalida(self):
        for opciones in ([],['A'],['A','a'],['A',''],['A',1],list('ABCDEFG')):
            with self.subTest(opciones=opciones), self.assertRaises(ValueError):
                _datos_publicacion(dict(BASE,tipo='encuesta',opciones_encuesta=opciones))
    def test_borrador_incompleto(self):
        self.assertEqual(_datos_publicacion({'titulo':''},borrador=True)['titulo'],'')
    def test_publicacion_incompleta(self):
        with self.assertRaises(ValueError):
            _datos_publicacion({'titulo':''})
    def test_id_booleano(self):
        with self.assertRaises(ValueError):
            _datos_publicacion(dict(BASE,id_categoria=True))

@unittest.skipUnless(DEPENDENCIAS, "Faltan dependencias del backend")
class Endpoints(unittest.TestCase):
    def setUp(self):
        self.con = MagicMock()
        self.cur = self.con.cursor.return_value
        self.cur.__enter__.return_value = self.cur
        parche = patch.object(ConexionPostgres,'connection',new=property(lambda _: self.con))
        parche.start(); self.addCleanup(parche.stop)
        self.usuario = dict(id=7,correo='test@example.org',rol='estudiante')
        self.headers = {'Authorization':'Bearer '+jwt.encode({'id':7,'exp':int(time.time())+600},Config.JWT_SECRET,algorithm='HS256')}
        self.pregunta = dict(BASE,id=1,id_usuario=7,tipo='encuesta',opciones_encuesta=['A','B'])
    def test_borrador_privado(self):
        self.cur.fetchone.side_effect = [self.usuario, {'datos':BASE}]
        r = foro.test_client().get('/preguntas/borrador',headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json, BASE)
        self.assertEqual(self.cur.execute.call_args.args[1],(7,))
        self.assertIn('no-store',r.headers['Cache-Control'])
    def test_borrador_sin_sesion(self):
        self.assertEqual(foro.test_client().get('/preguntas/borrador').status_code,401)
    def test_borrado_logico(self):
        self.cur.fetchone.side_effect = [self.usuario, {'id':1}, self.pregunta]
        r = foro.test_client().delete('/preguntas/1',headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertIn('fecha_eliminacion',self.cur.execute.call_args.args[0])
        self.con.commit.assert_called_once()
    def test_borrado_ajeno(self):
        self.cur.fetchone.side_effect = [self.usuario, {'id':1}, dict(self.pregunta,id_usuario=8)]
        r = foro.test_client().delete('/preguntas/1',headers=self.headers)
        self.assertEqual(r.status_code,403)
        self.con.commit.assert_not_called()
    def test_aceptar_respuesta_de_otro_hilo(self):
        self.cur.fetchone.side_effect = [self.usuario, {'id':1}, self.pregunta, None]
        r=foro.test_client().put('/preguntas/1/aceptar',json={'id_respuesta':42},headers=self.headers)
        self.assertEqual(r.status_code,404)
        self.con.commit.assert_not_called()
    def test_encuesta_voto_fuera_de_rango(self):
        self.cur.fetchone.side_effect=[self.usuario,{'id':1},self.pregunta,{'bloqueo':False}]
        r=foro.test_client().put('/preguntas/1/encuesta',json={'opcion':2},headers=self.headers)
        self.assertEqual(r.status_code,400)
        self.con.commit.assert_not_called()
    def test_encuesta_upsert(self):
        self.cur.fetchone.side_effect=[self.usuario,{'id':1},self.pregunta,{'bloqueo':False},{'opcion':0}]
        self.cur.fetchall.return_value=[{'opcion':0,'total':1}]
        r=foro.test_client().put('/preguntas/1/encuesta',json={'opcion':0},headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['mi_opcion'],0)
        self.assertTrue(any('ON CONFLICT' in c.args[0] for c in self.cur.execute.call_args_list))
    def test_comentario_padre_ajeno(self):
        self.cur.fetchone.side_effect=[self.usuario,{'id':1},{'id':3},None]
        r=interacciones.test_client().post('/comentarios',json={'id_respuesta':3,'id_comentario_padre':4,'contenido':'Hola'},headers=self.headers)
        self.assertEqual(r.status_code,404)
        self.con.commit.assert_not_called()

if __name__ == '__main__': unittest.main()
