"""Pruebas aisladas del código real, sin Flask ni base de datos. No prueban SQL en PostgreSQL."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

ROOT=Path(__file__).resolve().parents[1]
def cargar(ruta, nombres=None, constantes=()):
    ruta=ROOT/ruta
    nodos=[]
    for n in ast.parse(ruta.read_text()).body:
        if isinstance(n,ast.FunctionDef) and (nombres is None or n.name in nombres):
            n.decorator_list=[]; nodos.append(n)
        elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constantes for t in n.targets): nodos.append(n)
    ns={'jsonify':lambda *a,**kw:a[0] if a else kw}
    exec(compile(ast.Module(body=nodos,type_ignores=[]),str(ruta),'exec'),ns)
    return ns

class Moderacion(unittest.TestCase):
    def setUp(self):
        self.ns=cargar('routes/moderacion.py',constantes=('MOTIVOS','DESTINOS'))
        self.cur=MagicMock(); self.cur.__enter__.return_value=self.cur
        self.con=MagicMock(); self.con.cursor.return_value=self.cur
        self.ns.update(mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':1,'rol':'admin'}),request=SimpleNamespace(args={},get_json=lambda:{}))
    def llamar(self,funcion,datos=None,*args):
        self.ns['request'].get_json=lambda:datos or {}
        return self.ns[funcion](*args)
    def test_reporte_valido_parametrizado(self):
        self.cur.fetchone.side_effect=[{'autor':2},{'id':9}]
        resultado=self.llamar('crear_reporte',{'tipo':'pregunta','id_objeto':5,'motivo':'spam','detalle':"';--"})
        self.assertEqual(resultado[1],201)
        sql,params=self.cur.execute.call_args.args
        self.assertIn('ON CONFLICT',sql); self.assertNotIn("';--",sql); self.assertEqual(params,(1,'pregunta',5,'spam',"';--")); self.con.commit.assert_called_once()
    def test_reporte_duplicado(self):
        self.cur.fetchone.side_effect=[{'autor':2},None]
        self.assertEqual(self.llamar('crear_reporte',{'tipo':'pregunta','id_objeto':5,'motivo':'spam'})[1],409); self.con.commit.assert_not_called()
    def test_reporte_propio(self):
        self.cur.fetchone.return_value={'autor':1}
        self.assertEqual(self.llamar('crear_reporte',{'tipo':'usuario','id_objeto':1,'motivo':'spam'})[1],400); self.con.commit.assert_not_called()
    def test_reporte_no_existe(self):
        self.cur.fetchone.return_value=None
        self.assertEqual(self.llamar('crear_reporte',{'tipo':'comentario','id_objeto':10,'motivo':'spam'})[1],404)
    def test_validaciones(self):
        base={'tipo':'usuario','id_objeto':3,'motivo':'spam'}
        for cambio in ({'tipo':[]},{'tipo':'x'},{'motivo':'x'},{'id_objeto':True},{'id_objeto':-1},{'detalle':'x'*501},{'detalle':None}):
            with self.subTest(cambio=cambio): self.assertEqual(self.llamar('crear_reporte',dict(base,**cambio))[1],400)
        self.cur.execute.assert_not_called()
    def test_suspension(self):
        self.cur.fetchone.return_value={'rol':'estudiante','suspendido':False}
        self.assertEqual(self.llamar('suspension',{'activo':True,'motivo':'Spam'},2)[1],200)
        sql=[c.args[0] for c in self.cur.execute.call_args_list]; self.assertTrue(any('version_sesion=version_sesion+1' in s for s in sql)); self.assertTrue(any('historial_moderacion' in s for s in sql)); self.con.commit.assert_called_once()
    def test_no_suspender_admin(self):
        self.cur.fetchone.return_value={'rol':'admin','suspendido':False}
        self.assertEqual(self.llamar('suspension',{'activo':True,'motivo':'x'},2)[1],403); self.con.commit.assert_not_called()
    def test_suspension_motivo_requerido(self):
        self.assertEqual(self.llamar('suspension',{'activo':True},2)[1],400); self.cur.execute.assert_not_called()
    def test_suspension_idempotente(self):
        self.cur.fetchone.return_value={'rol':'estudiante','suspendido':True}
        self.assertEqual(self.llamar('suspension',{'activo':True,'motivo':'x'},2)[1],200); self.assertEqual(self.cur.execute.call_count,1)
    def test_moderar_pregunta(self):
        self.cur.fetchone.return_value={'fijada':False,'cerrada':False}
        self.assertEqual(self.llamar('moderar_pregunta',{'fijada':True,'cerrada':True},2),({'fijada':True,'cerrada':True},200)); self.assertEqual(self.cur.execute.call_count,5); self.con.commit.assert_called_once()
    def test_moderar_campo_invalido(self):
        self.assertEqual(self.llamar('moderar_pregunta',{'fijada':1},2)[1],400); self.cur.execute.assert_not_called()
    def test_revisar_reporte(self):
        self.cur.fetchone.return_value={'id':2}
        self.assertEqual(self.llamar('revisar_reporte',{'estado':'atendido'},2)[1],200); self.assertIn('estado=\'pendiente\'',self.cur.execute.call_args_list[0].args[0]); self.con.commit.assert_called_once()
    def test_revisar_reporte_ya_revisado(self):
        self.cur.fetchone.return_value=None
        self.assertEqual(self.llamar('revisar_reporte',{'estado':'descartado'},2)[1],409); self.con.commit.assert_not_called()
    def test_paginacion_reportes(self):
        self.ns['request'].args={'limite':'1','estado':'todos'}; self.cur.fetchall.return_value=[{'id':5},{'id':4}]
        r,status=self.ns['listar_reportes'](); self.assertEqual((status,r['siguiente'],r['elementos'][0]['id']),(200,'5','5'))
    def test_paginacion_invalida(self):
        self.ns['request'].args={'limite':'101'}; self.assertEqual(self.ns['historial']()[1],400); self.cur.execute.assert_not_called()

class Seguridad(unittest.TestCase):
    def setUp(self):
        self.ns=cargar('security.py',{'_usuario_desde_token'})
        self.cur=MagicMock(); self.cur.__enter__.return_value=self.cur; self.con=MagicMock(); self.con.cursor.return_value=self.cur
        class Context(dict):
            __setattr__=dict.__setitem__; __getattr__=dict.__getitem__
        self.jwt=MagicMock(); self.jwt.decode.return_value={'id':7,'version_sesion':0}
        self.ns.update(g=Context(),jwt=self.jwt,request=SimpleNamespace(headers={'Authorization':'Bearer token'}),Config=SimpleNamespace(JWT_SECRET='test',JWT_ALGORITHM='HS256'),mysql=SimpleNamespace(connection=self.con))
    def test_cuenta_suspendida(self):
        self.cur.fetchone.return_value={'id':7,'suspendido':True,'version_sesion':1}
        self.assertEqual(self.ns['_usuario_desde_token']()[1][1],401)
    def test_token_revocado_tras_reactivar(self):
        self.cur.fetchone.return_value={'id':7,'suspendido':False,'version_sesion':2}
        self.assertEqual(self.ns['_usuario_desde_token']()[1][1],401)
    def test_token_nuevo(self):
        self.jwt.decode.return_value={'id':7,'version_sesion':2}
        self.cur.fetchone.return_value={'id':7,'suspendido':False,'version_sesion':2}
        self.assertIsNone(self.ns['_usuario_desde_token']()[1])
    def test_token_anterior_migracion(self):
        self.jwt.decode.return_value={'id':7}; self.cur.fetchone.return_value={'id':7,'suspendido':False,'version_sesion':0}
        self.assertIsNone(self.ns['_usuario_desde_token']()[1])

class Conversaciones(unittest.TestCase):
    def test_respuestas_cerradas(self): self._cerrada('respuestas','respuesta',{'id_pregunta':2,'contenido':'hola'})
    def test_comentarios_cerrados(self): self._cerrada('comentarios','comentario',{'id_respuesta':2,'contenido':'hola'})
    def _cerrada(self,archivo,tipo,datos):
        ns=cargar('routes/'+archivo+'.py',{'crear_'+tipo}); cur=MagicMock(); cur.fetchone.return_value={'id':2,'cerrada':True}; con=MagicMock(); con.cursor.return_value=cur
        ns.update(g=SimpleNamespace(usuario={'id':7}),mysql=SimpleNamespace(connection=con),request=SimpleNamespace(get_json=lambda **kw:datos))
        self.assertEqual(ns['crear_'+tipo]()[1],409); con.commit.assert_not_called(); self.assertIn('FOR UPDATE',cur.execute.call_args.args[0])

# Pruebas HTTP con la conexión simulada, cuando estén las dependencias instaladas.
try:
    import flask, psycopg2, jwt
except ImportError:
    DEPENDENCIAS=False
else:
    import os, sys, time
    from unittest.mock import patch
    DEPENDENCIAS=True
    sys.path.insert(0,str(ROOT))
    os.environ['DATABASE_URL']='postgresql://test:test@127.0.0.1:1/test'
    os.environ['JWT_SECRET']='clave-de-pruebas-locales-no-productiva'
    from app_usuarios import app
    from app_interacciones import app as interacciones
    from config import Config
    from extensions import ConexionPostgres

@unittest.skipUnless(DEPENDENCIAS,'Faltan dependencias del backend')
class HTTP(unittest.TestCase):
    def setUp(self):
        self.con=MagicMock(); self.cur=self.con.cursor.return_value; self.cur.__enter__.return_value=self.cur
        parche=patch.object(ConexionPostgres,'connection',new=property(lambda _:self.con)); parche.start(); self.addCleanup(parche.stop)
        self.headers={'Authorization':'Bearer '+jwt.encode({'id':7,'exp':int(time.time())+600},Config.JWT_SECRET,algorithm='HS256')}
        self.cliente=app.test_client()
        self.identidad={'id':7,'rol':'estudiante','suspendido':False,'version_sesion':0}
    def test_sin_token(self):
        self.assertEqual(self.cliente.get('/moderacion/reportes').status_code,401)
        self.assertEqual(self.cliente.post('/moderacion/reportes',json={}).status_code,401)
    def test_no_admin(self):
        self.cur.fetchone.return_value=self.identidad
        for ruta in ('/moderacion/reportes','/moderacion/historial','/moderacion/estadisticas'):
            self.assertEqual(self.cliente.get(ruta,headers=self.headers).status_code,403)
        self.assertEqual(self.cliente.put('/moderacion/usuarios/8/suspension',headers=self.headers,json={'activo':True,'motivo':'spam'}).status_code,403)
        self.assertEqual(self.cliente.put('/moderacion/preguntas/2',headers=self.headers,json={'cerrada':True}).status_code,403)
        self.con.commit.assert_not_called()
    def test_token_suspendido(self):
        self.cur.fetchone.return_value=dict(self.identidad,suspendido=True,version_sesion=1)
        self.assertEqual(self.cliente.get('/usuarios/7',headers=self.headers).status_code,401)
    def test_conversacion_cerrada(self):
        self.cur.fetchone.side_effect=[self.identidad,{'id':2,'cerrada':True}]
        self.assertEqual(interacciones.test_client().post('/respuestas',headers=self.headers,json={'id_pregunta':2,'contenido':'hola'}).status_code,409)
        self.con.commit.assert_not_called()

if __name__=='__main__': unittest.main()
