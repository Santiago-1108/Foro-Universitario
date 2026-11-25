"""Regresiones del contrato; las pruebas SQL inspeccionan consultas, no ejecutan PostgreSQL."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from test_navegacion import funciones

class Contrato(unittest.TestCase):
    def setUp(self):
        self.cur=MagicMock(); self.cur.__enter__.return_value=self.cur; self.cur.fetchall.return_value=[]
        self.con=MagicMock(); self.con.cursor.return_value=self.cur
        self.ns=funciones('preguntas.py',{'_listar','_filtros_feed','_pregunta_publica'},{'SQL_PREGUNTA_DETALLE','ETIQUETAS','ORDENES'})
        self.ns.update(mysql=SimpleNamespace(connection=self.con))
    def feed(self, args, uid=None, categoria=None):
        self.ns.update(request=SimpleNamespace(args=args,headers={'Authorization':'Bearer prueba'} if uid else {}),_usuario_desde_token=lambda:({'id':uid,'rol':'estudiante'},None) if uid else (None,({'error':'Sin sesión'},401)))
        return self.ns['_listar'](categoria)
    def test_contrato_feed_combinaciones(self):
        for orden in ('para_ti','reciente','antiguo','popular','tendencias','relevancia'):
            for vista in ('todas','personalizado','historial','guardadas','ocultas','positivos','negativos'):
                with self.subTest(orden=orden,vista=vista):
                    self.assertEqual(self.feed(dict(orden=orden,vista=vista,limite='21',offset='20',etiqueta='duda',tipo='texto',estado='pendiente',q='Flask'),7,3),([],200))
                    sql,params=self.cur.execute.call_args.args
                    self.assertEqual(sql.count('%s'),len(params)); self.assertEqual(params[-2:],(21,20))
    def test_vista_privada_sin_sesion(self):
        for vista in ('historial','personalizado','guardadas','ocultas','positivos','negativos'):
            self.assertEqual(self.feed({'vista':vista})[1],401)
        self.cur.execute.assert_not_called()
    def test_detalle_parametro_invalido(self):
        for campo in ('orden','vista','tipo','estado','etiqueta'):
            cuerpo,status=self.feed({campo:'incorrecto'}); self.assertEqual(status,400); self.assertIn(campo,cuerpo['detalle'])
        self.cur.execute.assert_not_called()
    def test_paginacion_invalida(self):
        for args in ({'offset':'-1'},{'limite':'101'},{'limite':'x'}):
            cuerpo,status=self.feed(args); self.assertEqual(status,400); self.assertEqual(cuerpo['detalle'],'Paginación inválida')
    def test_historial_vacio_correcto(self):
        self.assertEqual(self.feed({'vista':'historial','orden':'reciente','limite':'21','offset':'0'},7),([],200))
    def test_votos_signos_y_tipos(self):
        ns=funciones('usuarios.py',{'votos_personales','_offset_actividad'});ns.update(mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}))
        for signo in ('1','-1'):
            for tipo in ('','publicacion','respuesta'):
                ns['request']=SimpleNamespace(args={'signo':signo,'tipo':tipo,'offset':'20','id_usuario':'99'})
                self.assertEqual(ns['votos_personales'](),{'actividad':[],'hay_mas':False})
                sql,params=self.cur.execute.call_args.args
                self.assertEqual(sql.count('%s'),len(params));self.assertEqual(params[:7],(7,int(signo),7,7,int(signo),7,7));self.assertNotIn(99,params)
                if tipo: self.assertEqual(params[-2:],(tipo,20))
    def test_votos_tipo_no_admitido(self):
        ns=funciones('usuarios.py',{'votos_personales','_offset_actividad'}); ns.update(request=SimpleNamespace(args={'tipo':'comentario'}))
        self.assertEqual(ns['votos_personales']()[1],400)

class HTTPContrato(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from test_modulo1 import usuarios_app, foro_app, interacciones_app
        except (ImportError, unittest.SkipTest):
            raise unittest.SkipTest('Faltan dependencias Flask/psycopg2')
        cls.apps=(usuarios_app,foro_app,interacciones_app)
    def test_revision_servicios(self):
        for app,modulo in zip(self.apps,('usuarios','preguntas','votos')):
            r=app.test_client().get('/estado-api');self.assertEqual(r.status_code,200);self.assertEqual(r.json['revision'],'comunidades-multimedia-1');self.assertIn(modulo,r.json['modulos']);self.assertEqual(r.headers['X-Foro-Revision'],'comunidades-multimedia-1')
    def test_error_json_y_metodo(self):
        for app in self.apps:
            r=app.test_client().get('/ruta-inexistente');self.assertEqual(r.status_code,404);self.assertIn('error',r.json)
            r=app.test_client().post('/estado-api',json={});self.assertEqual(r.status_code,405);self.assertIn('GET',r.headers['Allow'])
    def test_votos_privados_sin_token(self):
        r=self.apps[0].test_client().get('/usuarios/perfil/votos?signo=1&tipo=respuesta&offset=0');self.assertEqual(r.status_code,401)
    def test_historial_sin_token(self):
        r=self.apps[1].test_client().get('/preguntas?vista=historial&orden=reciente&limite=21&offset=0');self.assertEqual(r.status_code,401)
