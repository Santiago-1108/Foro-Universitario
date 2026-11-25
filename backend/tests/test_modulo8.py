"""Regresiones aisladas del código real; no ejecutan Flask ni SQL real."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]

def cargar(ruta, funciones, constantes=()):
    p = ROOT / ruta
    nodos = []
    for n in ast.parse(p.read_text()).body:
        if isinstance(n, ast.FunctionDef) and n.name in funciones:
            n.decorator_list = []
            nodos.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id in constantes for t in n.targets):
            nodos.append(n)
    ns = {'jsonify': lambda *a, **kw: a[0] if a else kw}
    exec(compile(ast.Module(body=nodos,type_ignores=[]),str(p),'exec'),ns)
    return ns

class Cuentas(unittest.TestCase):
    def setUp(self):
        self.ns=cargar('routes/usuarios.py', ['actualizar_usuario','usuario_actual','_buscar_usuario','_usuario_publico'], ['ROLES_VALIDOS'])
        self.con=MagicMock(); self.cur=self.con.cursor.return_value; self.cur.__enter__.return_value=self.cur
        self.actor=dict(id=1,rol='estudiante',suspendido=False,version_sesion=0,nombre_apellido='Prueba',correo='a@example.invalid',password_hash='hash')
        self.cur.fetchall.return_value=[self.actor]
        self.cur.fetchone.return_value=dict(self.actor,fecha_registro='2026-01-01')
        self.ns.update(mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario=dict(self.actor)),request=SimpleNamespace(get_json=lambda **kw:{}),check_password_hash=lambda h,p:p=='correcta',generate_password_hash=lambda p:'nuevo-hash')
    def llamar(self,datos,id=1):
        self.ns['request'].get_json=lambda **kw:datos
        return self.ns['actualizar_usuario'](id)
    def test_rol_no_autorizado(self):
        self.assertEqual(self.llamar({'rol':'admin'})[1],403); self.con.commit.assert_not_called()
    def test_otra_cuenta_no_autorizada(self):
        self.assertEqual(self.llamar({'nombre_apellido':'Cambio'},2)[1],403)
    def test_revalidacion_sesion(self):
        self.cur.fetchall.return_value=[dict(self.actor,version_sesion=1)]
        self.assertEqual(self.llamar({'nombre_apellido':'Cambio'})[1],401); self.con.commit.assert_not_called()
    def test_cambio_nombre_no_revoca(self):
        self.assertEqual(self.llamar({'nombre_apellido':'Cambio'})[1],200)
        update=[x.args for x in self.cur.execute.call_args_list if 'UPDATE usuarios SET' in x.args[0]][0]
        self.assertEqual(update[1][-2],0); self.con.commit.assert_called_once()
    def test_password_corta(self):
        self.assertEqual(self.llamar({'password':'123'})[1],400)
    def test_password_sin_confirmacion(self):
        self.assertEqual(self.llamar({'password':'password-nueva'})[1],403); self.con.commit.assert_not_called()
    def test_password_revoca(self):
        self.assertEqual(self.llamar({'password':'password-nueva','password_actual':'correcta'})[1],200)
        update=[x.args for x in self.cur.execute.call_args_list if 'UPDATE usuarios SET' in x.args[0]][0]
        self.assertEqual(update[1][-3:],('nuevo-hash',1,1)); self.con.commit.assert_called_once()
    def test_email_requiere_confirmacion(self):
        self.assertEqual(self.llamar({'correo':'b@example.invalid'})[1],403)
    def test_no_degradar_admin(self):
        self.actor['rol']='admin'; self.ns['g'].usuario['rol']='admin'
        self.assertEqual(self.llamar({'rol':'estudiante'})[1],409); self.con.commit.assert_not_called()
    def test_yo_no_expone_hash(self):
        datos,status=self.ns['usuario_actual']()
        self.assertEqual(status,200); self.assertNotIn('password_hash',datos); self.assertNotIn('version_sesion',datos)

class Validacion(unittest.TestCase):
    def test_json_rechaza_tipos(self):
        ns=cargar('extensions.py',['validar_json'],['LIMITES_TEXTO'])
        for datos in ([], {'titulo':True},{'contenido':'x'*2001},{'id_categoria':True},{'correo':'x y@z'}):
            ns['request']=SimpleNamespace(method='POST',get_json=lambda **kw:datos)
            self.assertEqual(ns['validar_json']()[1],400)
    def test_borrador_anidado_incompleto(self):
        ns=cargar('extensions.py',['validar_json'],['LIMITES_TEXTO'])
        ns['request']=SimpleNamespace(method='PUT',get_json=lambda **kw:{'datos':{'titulo':'','contenido':''}})
        self.assertIsNone(ns['validar_json']())
    def test_setup_no_crea_cuentas(self):
        sql=(ROOT/'database/setup.sql').read_text().upper()
        self.assertNotIn('INSERT INTO USUARIOS',sql); self.assertNotIn('DROP TABLE',sql); self.assertNotIn('TRUNCATE',sql)
    def test_migracion_no_borra_datos(self):
        sql=(ROOT/'database/migrations/008_auditoria_seguridad.sql').read_text().upper()
        for prohibido in ('DROP TABLE','TRUNCATE','DELETE FROM','UPDATE PUBLIC.'):
            self.assertNotIn(prohibido,sql)
        self.assertIn('REVOKE ALL',sql)

if __name__=='__main__': unittest.main()
