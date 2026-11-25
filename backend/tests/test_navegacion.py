"""Pruebas de regresión de consultas y permisos, sin acceso a producción."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import urlsplit

BASE=Path(__file__).resolve().parents[1]
def funciones(archivo,nombres,constantes=()):
    ruta=BASE/'routes'/archivo
    nodos=[]
    for n in ast.parse(ruta.read_text(encoding='utf-8')).body:
        if isinstance(n,ast.FunctionDef) and n.name in nombres:
            n.decorator_list=[];nodos.append(n)
        elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constantes for t in n.targets): nodos.append(n)
    ns={'jsonify':lambda *a,**k:a[0] if a else k,'urlsplit':urlsplit}
    exec(compile(ast.Module(body=nodos,type_ignores=[]),str(ruta),'exec'),ns)
    return ns

class Navegacion(unittest.TestCase):
    def setUp(self):
        self.ns=funciones('preguntas.py',{'_listar','_filtros_feed','_pregunta_publica','registrar_visita','limpiar_historial','buscar_interacciones'}, {'SQL_PREGUNTA_DETALLE','ETIQUETAS','ORDENES'})
        self.cur=MagicMock();self.cur.__enter__.return_value=self.cur;self.cur.fetchall.return_value=[]
        self.con=MagicMock();self.con.cursor.return_value=self.cur
        self.ns.update(mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}))
    def peticion(self,args,uid=None):
        self.ns['request']=SimpleNamespace(args=args,headers={'Authorization':'Bearer prueba'} if uid else {})
        self.ns['_usuario_desde_token']=lambda:({'id':uid,'rol':'estudiante'},None) if uid else (None,({'error':'Sin sesión'},401))
    def consulta(self):
        sql,params=self.cur.execute.call_args.args
        self.assertEqual(sql.count('%s'),len(params));return sql,params
    def test_historial_sin_sesion(self):
        self.peticion({'vista':'historial'});self.assertEqual(self.ns['_listar']()[1],401);self.cur.execute.assert_not_called()
    def test_historial_propio(self):
        self.peticion({'vista':'historial'},7);self.ns['_listar']();sql,params=self.consulta();self.assertIn('historial_preguntas',sql);self.assertIn('fecha_visita',sql);self.assertEqual(params,(7,7,7,7,20,0))
    def test_historial_orden_relevancia(self):
        self.peticion({'vista':'historial','q':'Flask','orden':'relevancia'},7);self.ns['_listar']();sql,params=self.consulta();self.assertNotIn('strpos(lower(f.titulo)',sql);self.assertEqual(params.count('Flask'),4)
    def test_registrar_visita(self):
        self.cur.fetchone.return_value={'id':4};self.ns['registrar_visita'](4);sql,params=self.consulta();self.assertIn('ON CONFLICT',sql);self.assertEqual(params,(7,4));self.con.commit.assert_called_once()
    def test_visita_bloqueada_o_inexistente(self):
        self.cur.fetchone.return_value=None;self.assertEqual(self.ns['registrar_visita'](4)[1],404);self.con.commit.assert_not_called()
    def test_limpiar_historial_propio(self):
        self.ns['limpiar_historial']();sql,params=self.consulta();self.assertIn('WHERE id_usuario=%s',sql);self.assertEqual(params,(7,))
    def test_filtros_publicaciones(self):
        self.peticion({'dias':'7','min_votos':'5','autor':'9'});self.ns['_listar']();sql,params=self.consulta();self.assertIn('p.id_usuario=%s',sql);self.assertIn('interval',sql);self.assertEqual(params,(9,7,5,20,0))
    def test_filtro_invalido(self):
        for a in ({'dias':'2'},{'min_votos':'no'},{'autor':'0'}):
            self.peticion(a);self.assertEqual(self.ns['_listar']()[1],400)
        self.cur.execute.assert_not_called()
    def test_buscar_interacciones_parametrizado(self):
        q="'; -- %_";self.peticion({'q':q,'categoria':'3','dias':'7','min_votos':'2'},7);r=self.ns['buscar_interacciones']();sql,params=self.consulta();self.assertNotIn(q,sql);self.assertIn('UNION ALL',sql);self.assertIn('foro_hay_bloqueo',sql);self.assertEqual(params,(7,7,7,7,7,q,2,7,3,7,q,0));self.assertEqual(r['resultados'],[])
    def test_buscar_interacciones_invalido(self):
        self.peticion({'q':'a','orden':'DROP'});self.assertEqual(self.ns['buscar_interacciones']()[1],400);self.cur.execute.assert_not_called()
    def test_portada_validada(self):
        ns=funciones('usuarios.py',{'_datos_perfil'});self.assertEqual(ns['_datos_perfil']({'portada_url':'https://example.org/a.png'}),{'portada_url':'https://example.org/a.png'})
        for url in ('javascript:alert(1)','http://example.org/a',None):
            with self.assertRaises(ValueError):ns['_datos_perfil']({'portada_url':url})
    def test_votos_personales_consulta(self):
        ns=funciones('usuarios.py',{'_offset_actividad','votos_personales'});ns.update(mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}),request=SimpleNamespace(args={'signo':'-1','id_usuario':'99'}));ns['votos_personales']();sql,params=self.consulta();self.assertIn('UNION ALL',sql);self.assertEqual(params,(7,-1,7,7,-1,7,7,0));self.assertNotIn(99,params)
    def test_migracion_incremental(self):
        s=(BASE/'database/migrations/009_navegacion_perfil.sql').read_text(encoding='utf-8').upper();self.assertIn('ENABLE ROW LEVEL SECURITY',s);self.assertIn('REVOKE ALL',s);self.assertNotIn('DROP TABLE',s);self.assertNotIn('TRUNCATE',s)
if __name__=='__main__':unittest.main()
