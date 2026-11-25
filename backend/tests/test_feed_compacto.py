"""Regresiones de clasificación y consultas; no requieren una BD real."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from test_navegacion import funciones

class FeedCompacto(unittest.TestCase):
    def setUp(self):
        self.cur=MagicMock();self.cur.__enter__.return_value=self.cur;self.cur.fetchall.return_value=[]
        self.con=MagicMock();self.con.cursor.return_value=self.cur
        self.ns=funciones('preguntas.py',{'_listar','_filtros_feed','_pregunta_publica'},{'SQL_PREGUNTA_DETALLE','ETIQUETAS','ORDENES'})
        self.ns.update(mysql=SimpleNamespace(connection=self.con))
    def consulta(self,args,uid=None):
        self.ns['request']=SimpleNamespace(args=args,headers={'Authorization':'Bearer prueba'} if uid else {})
        self.ns['_usuario_desde_token']=lambda:({'id':uid,'rol':'estudiante'},None) if uid else (None,({'error':'Sin sesión'},401))
        self.assertEqual(self.ns['_listar']()[1],200)
        sql,params=self.cur.execute.call_args.args
        self.assertEqual(sql.count('%s'),len(params));return sql,params
    def test_recomendadas_publicas(self):
        sql,params=self.consulta({'orden':'para_ti'});self.assertIn('power(',sql);self.assertNotIn('seguimientos_usuarios',sql);self.assertEqual(params,(20,0))
    def test_recomendadas_autenticadas(self):
        sql,params=self.consulta({'orden':'para_ti'},7);self.assertIn('THEN 1.5',sql);self.assertIn('foro_hay_bloqueo',sql);self.assertIn('preguntas_ocultas',sql);self.assertEqual(params,(7,7,7,7,7,20,0))
    def test_siguiendo_union_sin_duplicados(self):
        sql,params=self.consulta({'vista':'personalizado'},7);self.assertIn('OR EXISTS(SELECT 1 FROM seguimientos_usuarios',sql);self.assertEqual(params,(7,7,7,7,7,20,0))
    def test_historial_con_orden_recomendadas(self):
        sql,params=self.consulta({'vista':'historial','orden':'para_ti'},7);self.assertIn('fecha_visita',sql);self.assertNotIn('THEN 1.5',sql);self.assertEqual(params,(7,7,7,7,20,0))
    def test_actividad_filtros_antes_paginacion(self):
        ns=funciones('usuarios.py',{'actividad','_offset_actividad'});ns.update(mysql=SimpleNamespace(connection=self.con));self.cur.fetchone.return_value={'id':3}
        for tipo in ('publicacion','respuesta','comentario',''):
            ns['request']=SimpleNamespace(args={'tipo':tipo,'offset':'20'},headers={});ns['actividad'](3)
            sql,params=self.cur.execute.call_args.args;self.assertIn("WHERE (%s='' OR tipo=%s) ORDER BY",sql);self.assertEqual(params[-3:],(tipo,tipo,20));self.assertEqual(sql.count('%s'),len(params))
    def test_actividad_tipo_invalido(self):
        ns=funciones('usuarios.py',{'actividad','_offset_actividad'});ns.update(request=SimpleNamespace(args={'tipo':'otro'},headers={}),mysql=SimpleNamespace(connection=self.con));self.assertEqual(ns['actividad'](3)[1],400);self.cur.execute.assert_not_called()

    def test_votos_filtrados_privados(self):
        ns=funciones('usuarios.py',{'votos_personales','_offset_actividad'});ns.update(mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}),request=SimpleNamespace(args={'signo':'1','tipo':'publicacion','id_usuario':'99'}));ns['votos_personales']()
        sql,params=self.cur.execute.call_args.args;self.assertIn('WHERE tipo=%s ORDER BY',sql);self.assertEqual(params,(7,1,7,7,1,7,7,'publicacion',0));self.assertNotIn(99,params)
