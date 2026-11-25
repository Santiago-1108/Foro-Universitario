"""Validación y construcción SQL sin red ni dependencias; no prueba PostgreSQL real."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import urlsplit

RUTA = Path(__file__).resolve().parents[1] / 'routes/preguntas.py'
NOMBRES = {'ETIQUETAS','ORDENES','SQL_PREGUNTA_DETALLE'}
FUNCIONES = {'_filtros_feed','_datos_publicacion','_listar','_pregunta_publica'}
mod = ast.parse(RUTA.read_text(encoding='utf-8'))
nodos = [n for n in mod.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in NOMBRES for t in n.targets)) or (isinstance(n,ast.FunctionDef) and n.name in FUNCIONES)]
ns = {'urlsplit':urlsplit, 'jsonify':lambda *args,**kw: args[0] if args else kw}
exec(compile(ast.Module(body=nodos,type_ignores=[]),str(RUTA),'exec'),ns)

class Validacion(unittest.TestCase):
    def test_filtros_por_defecto(self):
        self.assertEqual(ns['_filtros_feed']({}), ('','reciente','todas','','','',20,0))
    def test_filtros_validos(self):
        self.assertEqual(ns['_filtros_feed']({'q':' Vue ','orden':'relevancia','vista':'guardadas','tipo':'enlace','estado':'resuelta','etiqueta':'recurso','limite':'21','offset':'20'}),('Vue','relevancia','guardadas','recurso','enlace','resuelta',21,20))
    def test_filtros_invalidos(self):
        for args in ({'q':'a'*121},{'q':'a\x00'},{'orden':'p.id; --'},{'vista':'admin'},{'tipo':'x'},{'etiqueta':'x'},{'estado':'x'},{'offset':'-1'},{'limite':'101'},{'limite':'0'},{'offset':'abc'}):
            with self.subTest(args=args),self.assertRaises(ValueError): ns['_filtros_feed'](args)
    def test_etiqueta_publicacion_y_borrador(self):
        self.assertEqual(ns['_datos_publicacion']({'id_categoria':1,'titulo':'T','contenido':'C','etiqueta':'duda'})['etiqueta'],'duda')
        self.assertEqual(ns['_datos_publicacion']({'etiqueta':'recurso'},True)['etiqueta'],'recurso')
        self.assertEqual(ns['_datos_publicacion']({},True)['etiqueta'],'')
    def test_etiqueta_invalida(self):
        for e in (None,True,[], 'personalizada'):
            with self.subTest(e=e),self.assertRaises(ValueError): ns['_datos_publicacion']({'etiqueta':e},True)

class Consulta(unittest.TestCase):
    def setUp(self):
        self.cur=MagicMock(); self.cur.__enter__.return_value=self.cur; self.cur.fetchall.return_value=[]
        con=MagicMock(); con.cursor.return_value=self.cur; ns['mysql']=SimpleNamespace(connection=con)
    def consultar(self,args,uid=None,rol='estudiante',categoria=None):
        ns['request']=SimpleNamespace(args=args,headers={'Authorization':'Bearer fake'} if uid else {})
        ns['_usuario_desde_token']=lambda: ({'id':uid,'rol':rol},None) if uid else (None,({'error':'Sin sesión'},401))
        return ns['_listar'](categoria)
    def sql(self):
        sql,params=self.cur.execute.call_args.args
        self.assertEqual(sql.count('%s'),len(params))
        return sql,params
    def test_publico_paginado(self):
        self.assertEqual(self.consultar({}),([],200)); sql,params=self.sql(); self.assertEqual(params,(20,0)); self.assertIn('LIMIT %s OFFSET %s',sql)
    def test_busqueda_parametrizada(self):
        q="'; -- %_"
        self.consultar({'q':q,'orden':'relevancia','limite':'21'},categoria=3)
        sql,params=self.sql(); self.assertNotIn(q,sql); self.assertEqual(params,(3,*([q]*6),21,0)); self.assertLess(sql.index('ORDER BY'),sql.index('LIMIT'))
    def test_personalizado(self):
        self.consultar({'vista':'personalizado','estado':'resuelta'},7)
        sql,params=self.sql(); self.assertIn('seguimientos_usuarios',sql); self.assertIn('seguimientos_categorias',sql); self.assertIn('foro_hay_bloqueo',sql); self.assertIn('id_respuesta_aceptada IS NOT NULL',sql); self.assertEqual(params,(7,7,7,7,7,20,0))
    def test_guardadas(self):
        self.consultar({'vista':'guardadas'},7); sql,_=self.sql(); self.assertIn('preguntas_guardadas',sql); self.assertIn('NOT EXISTS (SELECT 1 FROM preguntas_ocultas',sql)
    def test_ocultas(self):
        self.consultar({'vista':'ocultas'},7); sql,_=self.sql(); self.assertIn('AND EXISTS (SELECT 1 FROM preguntas_ocultas',sql)
    def test_privado_sin_sesion(self):
        self.assertEqual(self.consultar({'vista':'guardadas'})[1],401); self.cur.execute.assert_not_called()
    def test_gestion_no_admin(self):
        self.assertEqual(self.consultar({'gestion':'1'},7)[1],403); self.cur.execute.assert_not_called()
    def test_gestion_admin(self):
        self.consultar({'gestion':'1'},7,'admin'); sql,params=self.sql(); self.assertNotIn('preguntas_ocultas',sql); self.assertNotIn('LIMIT %s',sql); self.assertEqual(params,())
    def test_tendencias(self):
        self.consultar({'orden':'tendencias'}); sql,_=self.sql(); self.assertIn('EXTRACT(EPOCH',sql); self.assertIn('cantidad_respuestas',sql)
    def test_ordenes(self):
        for orden,esperado in [('popular','total_votos DESC'),('antiguo','f.fecha_creacion ASC'),('reciente','f.fecha_creacion DESC')]:
            self.consultar({'orden':orden}); self.assertIn(esperado,self.sql()[0])

if __name__=='__main__': unittest.main()
