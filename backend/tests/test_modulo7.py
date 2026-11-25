"""Pruebas aisladas sobre las funciones reales. No sustituyen PostgreSQL ni HTTP."""
import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


def cargar():
    ruta = ROOT / 'routes/mensajes.py'
    nodos = []
    for n in ast.parse(ruta.read_text()).body:
        if isinstance(n, ast.FunctionDef):
            n.decorator_list = []
            nodos.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MAX_ID' for t in n.targets):
            nodos.append(n)
    ns = {'jsonify': lambda **kw: kw}
    exec(compile(ast.Module(body=nodos, type_ignores=[]), str(ruta), 'exec'), ns)
    return ns


class Mensajes(unittest.TestCase):
    def setUp(self):
        self.ns = cargar()
        self.cur = MagicMock(); self.cur.__enter__.return_value = self.cur
        self.con = MagicMock(); self.con.cursor.return_value = self.cur
        self.ns.update(mysql=SimpleNamespace(connection=self.con), g=SimpleNamespace(usuario={'id':1,'version_sesion':0}), request=SimpleNamespace(args={},get_json=lambda **kw:{}))
        self.contacto = {'id':2,'nombre_apellido':'Prueba','avatar_url':None,'suspendido':False}
        self.filas_usuarios = [{'id':1,'suspendido':False,'version_sesion':0},{'id':2,'suspendido':False,'version_sesion':0}]
        self.fila = {'id':9007199254740993,'id_emisor':2,'contenido':'hola','fecha_creacion':datetime.now(timezone.utc),'fecha_lectura':None}

    def test_par_canonico(self):
        self.assertEqual(self.ns['_par'](3,1),(1,3))
        for invalido in (3,0,-1,True,2**63):
            with self.assertRaises(ValueError): self.ns['_par'](3,invalido)

    def test_texto(self):
        self.assertEqual(self.ns['_contenido']({'contenido':' hola '}),'hola')
        for invalido in (None,False,[],{'contenido':False},{'contenido':'  '},{'contenido':'x'*2001},{'contenido':'\x00'}):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError): self.ns['_contenido'](invalido)

    def test_paginacion(self):
        self.assertEqual(self.ns['_pagina']({'limite':'50','antes':'123'}),(50,123))
        for invalido in ({'limite':'0'},{'limite':'51'},{'antes':'0'},{'antes':str(2**63)},{'antes':'xx'}):
            with self.assertRaises(ValueError): self.ns['_pagina'](invalido)

    def test_serializa_bigint(self):
        m = self.ns['_mensaje'](self.fila,1)
        self.assertEqual(m['id'],'9007199254740993'); self.assertFalse(m['propio']); self.assertFalse(m['leido'])
        self.assertNotIn('id_emisor',m)

    def test_contador_privado(self):
        self.ns['request'].args={'solo_conteo':'1'}; self.cur.fetchone.return_value={'pendientes':4}
        self.assertEqual(self.ns['bandeja'](),({'pendientes':4},200))
        sql,params=self.cur.execute.call_args.args; self.assertEqual(params,(1,1)); self.assertIn('IN (c.usuario_a,c.usuario_b)',sql); self.assertIn('foro_hay_bloqueo',sql)

    def test_bandeja_cursor(self):
        self.ns['request'].args={'limite':'1','antes':'100'}; self.cur.fetchone.return_value={'pendientes':1}
        fila=dict(self.fila,id=90,contacto=2,nombre_apellido='Prueba',avatar_url=None,suspendido=False,pendientes=1)
        self.cur.fetchall.return_value=[fila,dict(fila,id=80)]
        resultado,status=self.ns['bandeja'](); self.assertEqual(status,200); self.assertEqual(resultado['siguiente'],'90')
        sql,params=self.cur.execute.call_args.args; self.assertEqual(params,(1,1,1,100,2)); self.assertIn('m.id < %s',sql)

    def test_historial_privado(self):
        self.cur.fetchone.return_value=self.contacto; self.cur.fetchall.return_value=[dict(self.fila,id=9),dict(self.fila,id=8)]
        resultado,status=self.ns['historial'](2); self.assertEqual(status,200); self.assertEqual([m['id'] for m in resultado['mensajes']],['8','9'])
        sql,params=self.cur.execute.call_args.args; self.assertEqual(params,(1,2,21)); self.assertIn('c.usuario_a=%s AND c.usuario_b=%s',sql); self.assertIn('foro_hay_bloqueo',sql)

    def test_historial_bloqueado(self):
        self.cur.fetchone.return_value=None
        self.assertEqual(self.ns['historial'](2)[1],404); self.assertEqual(self.cur.execute.call_count,1)

    def preparar_envio(self,contenido='hola'):
        self.ns['request'].get_json=lambda **kw:{'contenido':contenido}; self.cur.fetchall.return_value=self.filas_usuarios

    def test_envio_parametrizado(self):
        self.preparar_envio("' OR 1=1 --"); self.cur.fetchone.side_effect=[self.contacto,{'cantidad':0},{'id':7},dict(self.fila,id_emisor=1)]
        resultado,status=self.ns['enviar'](2); self.assertEqual(status,201); self.assertTrue(resultado['mensaje']['propio'])
        sql,params=self.cur.execute.call_args.args; self.assertNotIn("' OR 1=1 --",sql); self.assertEqual(params,(7,1,"' OR 1=1 --")); self.con.commit.assert_called_once()

    def test_envio_bloqueado(self):
        self.preparar_envio(); self.cur.fetchone.return_value=None
        self.assertEqual(self.ns['enviar'](2)[1],404); self.con.commit.assert_not_called()

    def test_envio_suspendido(self):
        self.preparar_envio(); self.filas_usuarios[1]['suspendido']=True
        self.assertEqual(self.ns['enviar'](2)[1],403); self.con.commit.assert_not_called()

    def test_emisor_revocado(self):
        self.preparar_envio(); self.filas_usuarios[0]['version_sesion']=1
        self.assertEqual(self.ns['enviar'](2)[1],401); self.con.commit.assert_not_called()

    def test_limite_envio(self):
        self.preparar_envio(); self.cur.fetchone.side_effect=[self.contacto,{'cantidad':30}]
        self.assertEqual(self.ns['enviar'](2)[1],429); self.con.commit.assert_not_called()

    def test_no_enviar_a_si_mismo(self):
        self.preparar_envio(); self.assertEqual(self.ns['enviar'](1)[1],400); self.cur.execute.assert_not_called()

    def test_lectura_solo_recibidos(self):
        self.ns['request'].get_json=lambda **kw:{'hasta':'15'}; self.cur.fetchone.return_value={'id':7}; self.cur.rowcount=2
        self.assertEqual(self.ns['leer'](2),({'marcados':2},200))
        sql,params=self.cur.execute.call_args.args; self.assertEqual(params,(7,2,15)); self.assertIn('m.id_emisor=%s',sql); self.assertIn('m.id<=%s',sql); self.con.commit.assert_called_once()

    def test_lectura_id_ajeno(self):
        self.ns['request'].get_json=lambda **kw:{'hasta':'15'}; self.cur.fetchone.return_value=None
        self.assertEqual(self.ns['leer'](2)[1],404); self.con.commit.assert_not_called(); self.assertEqual(self.cur.execute.call_count,1)

    def test_lectura_datos_invalidos(self):
        for invalido in (1,True,'0','-1','x',str(2**63)):
            self.ns['request'].get_json=lambda **kw:{'hasta':invalido}
            self.assertEqual(self.ns['leer'](2)[1],400)
        self.cur.execute.assert_not_called()


if __name__ == '__main__': unittest.main()
