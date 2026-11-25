"""Pruebas aisladas de lógica y consultas; no sustituyen PostgreSQL ni Flask HTTP."""
import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

RUTA = Path(__file__).resolve().parents[1] / 'routes' / 'notificaciones.py'
# Extrae funciones originales sin decoradores para ejecutar incluso sin Flask instalado.
nodos = []
for nodo in ast.parse(RUTA.read_text(encoding='utf-8')).body:
    if isinstance(nodo, ast.FunctionDef):
        nodo.decorator_list = []
        nodos.append(nodo)
    elif isinstance(nodo, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MAX_ID' for t in nodo.targets):
        nodos.append(nodo)
ns = {'jsonify': lambda **kw: kw}
exec(compile(ast.Module(body=nodos, type_ignores=[]), str(RUTA), 'exec'), ns)


def fila(id=15, tipo='respuesta', leida=False, pregunta=3):
    fecha = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return dict(id=id, tipo=tipo, actor='María', id_actor=9, id_pregunta=pregunta,
                fecha_creacion=fecha, fecha_lectura=fecha if leida else None,
                id_destinatario=7, correo='privado@example.org')


class Validacion(unittest.TestCase):
    def test_defecto(self):
        self.assertEqual(ns['_parametros']({}), (False, 20, None))

    def test_conteo_paginado(self):
        self.assertEqual(ns['_parametros']({'solo_conteo':'1', 'limite':'50','antes':'99'}), (True,50,99))

    def test_parametros_invalidos(self):
        for args in ({'solo_conteo':'true'}, {'limite':'0'}, {'limite':'51'}, {'limite':'x'}, {'antes':'0'}, {'antes':'-1'}, {'antes':'9223372036854775808'}, {'antes':'1 OR 1=1'}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                ns['_parametros'](args)

    def test_serializacion_privada(self):
        resultado = ns['_publica'](fila(9223372036854775807))
        self.assertEqual(resultado['id'], '9223372036854775807')
        self.assertEqual(resultado['texto'], 'María respondió tu publicación.')
        self.assertFalse(resultado['leida'])
        self.assertNotIn('correo', resultado)
        self.assertNotIn('id_destinatario', resultado)
        self.assertTrue(resultado['fecha_creacion'].endswith('+00:00'))

    def test_tipos(self):
        for tipo in ('respuesta','comentario','mencion','voto','seguidor'):
            with self.subTest(tipo=tipo):
                self.assertTrue(ns['_publica'](fila(tipo=tipo))['texto'])
        r=ns['_publica'](fila(tipo='seguidor', leida=True, pregunta=None))
        self.assertTrue(r['leida']); self.assertIsNone(r['id_pregunta'])


class Consultas(unittest.TestCase):
    def setUp(self):
        self.cur=MagicMock(); self.cur.__enter__.return_value=self.cur
        self.con=MagicMock(); self.con.cursor.return_value=self.cur
        ns['mysql']=SimpleNamespace(connection=self.con)
        ns['g']=SimpleNamespace(usuario={'id':7, 'rol':'estudiante'})
        ns['request']=SimpleNamespace(args={})

    def test_conteo_solo_usuario(self):
        ns['request'].args={'solo_conteo':'1','id_destinatario':'999'}
        self.cur.fetchone.return_value={'pendientes':2}
        self.assertEqual(ns['listar_notificaciones'](), ({'pendientes':2},200))
        sql,params=self.cur.execute.call_args.args
        self.assertIn('foro_notificaciones_visibles',sql); self.assertEqual(params,(7,))
        self.assertEqual(self.cur.execute.call_count,1)

    def test_paginacion(self):
        ns['request'].args={'limite':'2','antes':'20'}
        self.cur.fetchone.return_value={'pendientes':3}; self.cur.fetchall.return_value=[fila(18),fila(17),fila(16)]
        r,status=ns['listar_notificaciones']()
        self.assertEqual(status,200); self.assertEqual(r['siguiente'],'17'); self.assertEqual(len(r['notificaciones']),2)
        sql,params=self.cur.execute.call_args.args
        self.assertIn('ORDER BY n.id DESC LIMIT %s',sql); self.assertEqual(params,(7,20,3))

    def test_fin_paginacion(self):
        self.cur.fetchone.return_value={'pendientes':0}; self.cur.fetchall.return_value=[]
        r,status=ns['listar_notificaciones'](); self.assertIsNone(r['siguiente']); self.assertEqual(r['notificaciones'],[])

    def test_rechaza_parametro_sin_consultar(self):
        ns['request'].args={'antes':'-1'}
        self.assertEqual(ns['listar_notificaciones']()[1],400); self.cur.execute.assert_not_called()

    def test_marcar_propia_idempotente(self):
        self.cur.fetchone.return_value={'id':1}
        self.assertEqual(ns['leer_notificacion'](1),({'leida':True},200))
        sql,params=self.cur.execute.call_args.args
        self.assertIn('COALESCE',sql); self.assertIn('id_destinatario=%s',sql); self.assertEqual(params,(7,1,7))
        self.con.commit.assert_called_once()

    def test_no_marcar_ajena_o_invisible(self):
        self.cur.fetchone.return_value=None
        self.assertEqual(ns['leer_notificacion'](1)[1],404); self.con.commit.assert_not_called()

    def test_id_fuera_rango(self):
        self.assertEqual(ns['leer_notificacion'](9223372036854775808)[1],404); self.cur.execute.assert_not_called()

    def test_marcar_todas_solo_propias_visibles(self):
        self.cur.rowcount=4
        self.assertEqual(ns['leer_todas'](),({'marcadas':4},200))
        sql,params=self.cur.execute.call_args.args
        self.assertIn('id_destinatario=%s',sql); self.assertIn('foro_notificaciones_visibles',sql); self.assertEqual(params,(7,7))
        self.con.commit.assert_called_once()


# Pruebas HTTP sin conexiones reales, cuando se instalen las dependencias.
try:
    import flask, psycopg2, jwt
except ImportError:
    DEPENDENCIAS = False
else:
    import os, sys, time
    from unittest.mock import patch
    DEPENDENCIAS = True
    sys.path.insert(0, str(RUTA.parents[1]))
    os.environ['DATABASE_URL'] = 'postgresql://test:test@127.0.0.1:1/test'
    os.environ['JWT_SECRET'] = 'clave-de-pruebas-locales-no-productiva'
    from config import Config
    from extensions import ConexionPostgres
    from app_usuarios import app

@unittest.skipUnless(DEPENDENCIAS, 'Faltan dependencias del backend')
class HTTP(unittest.TestCase):
    def setUp(self):
        self.con=MagicMock(); self.cur=self.con.cursor.return_value
        self.cur.__enter__.return_value=self.cur
        parche=patch.object(ConexionPostgres,'connection',new=property(lambda _:self.con))
        parche.start(); self.addCleanup(parche.stop)
        self.identidad={'id':7,'correo':'test@example.invalid','rol':'estudiante'}
        self.headers={'Authorization':'Bearer '+jwt.encode({'id':7,'exp':int(time.time())+600},Config.JWT_SECRET,algorithm='HS256')}
        self.cliente=app.test_client()

    def test_sin_token(self):
        self.assertEqual(self.cliente.get('/notificaciones').status_code,401)
        self.assertEqual(self.cliente.put('/notificaciones/leer-todas',json={}).status_code,401)

    def test_conteo_privado(self):
        self.cur.fetchone.side_effect=[self.identidad,{'pendientes':3}]
        r=self.cliente.get('/notificaciones?solo_conteo=1&id_destinatario=999',headers=self.headers)
        self.assertEqual(r.status_code,200); self.assertEqual(r.json,{'pendientes':3})
        self.assertIn('no-store',r.headers['Cache-Control'])

    def test_notificacion_ajena(self):
        self.cur.fetchone.side_effect=[self.identidad,None]
        r=self.cliente.put('/notificaciones/99/leer',json={},headers=self.headers)
        self.assertEqual(r.status_code,404); self.con.commit.assert_not_called()

    def test_marcar_todas(self):
        self.cur.fetchone.return_value=self.identidad; self.cur.rowcount=2
        r=self.cliente.put('/notificaciones/leer-todas',json={},headers=self.headers)
        self.assertEqual(r.status_code,200); self.assertEqual(r.json,{'marcadas':2})

if __name__=='__main__': unittest.main()
