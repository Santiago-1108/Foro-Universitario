"""Regresiones de validación, permisos y consultas; no usan Supabase real."""
import unittest,re,uuid
from types import SimpleNamespace
from unittest.mock import MagicMock
from pathlib import Path
from test_navegacion import funciones

class NuevasFunciones(unittest.TestCase):
    def setUp(self):
        self.cur=MagicMock();self.cur.__enter__.return_value=self.cur;self.cur.fetchall.return_value=[]
        self.con=MagicMock();self.con.cursor.return_value=self.cur
        self.c=funciones('comunidades.py',{'validar_comunidad','_gestor','gestionar_miembro','moderar','membresia'})
        self.c.update(re=re,mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}))
        self.m=funciones('multimedia.py',{'validar_archivo','validar_ids','firma_valida','adjuntar_archivos','adjuntar_personalizacion','reservar','_error_storage'}, {'TIPOS','MAX_USUARIO_BYTES','MAX_GLOBAL_BYTES'})
        self.m.update(uuid=uuid,mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}),_storage_config=lambda:None)
        self.d=dict(nombre='Desarrollo web',slug='desarrollo-web',descripcion='Foro de aprendizaje',tipo='publica',id_categoria=1)
    def test_publica_restringida(self):
        for tipo in ('publica','restringida'):self.assertEqual(self.c['validar_comunidad'](dict(self.d,tipo=tipo))['tipo'],tipo)
    def test_privada_deshabilitada(self):
        with self.assertRaises(ValueError):self.c['validar_comunidad'](dict(self.d,tipo='privada'))
    def test_slug_invalido(self):
        for v in ('../admin','aa','Aaa','hola mundo','a'*41):
            with self.assertRaises(ValueError):self.c['validar_comunidad'](dict(self.d,slug=v))
    def test_tematica_y_url(self):
        for x in ({'id_categoria':True},{'id_categoria':0},{'portada_url':'javascript:alert(1)'},{'icono_url':'https://u:p@ejemplo.com/x'}):
            with self.assertRaises(ValueError):self.c['validar_comunidad']({**self.d,**x})
    def test_miembro_no_puede_asignar_moderador(self):
        self.c['request']=SimpleNamespace(get_json=lambda:{'accion':'moderador'});self.cur.fetchone.return_value={'mi_rol':'miembro','id_propietario':8}
        self.assertEqual(self.c['gestionar_miembro'](1,9)[1],403);self.con.commit.assert_not_called()
    def test_propietario_no_expulsable(self):
        self.c['request']=SimpleNamespace(get_json=lambda:{'accion':'expulsar'});self.cur.fetchone.return_value={'mi_rol':'propietario','id_propietario':7}
        self.assertEqual(self.c['gestionar_miembro'](1,7)[1],403);self.con.commit.assert_not_called()
    def test_moderar_limitado_a_comunidad(self):
        self.c['request']=SimpleNamespace(get_json=lambda:{'accion':'cerrada','valor':True});self.cur.fetchone.return_value={'mi_rol':'moderador','id_propietario':8};self.cur.rowcount=1
        self.assertEqual(self.c['moderar'](12,99),{'ok':True});sql,params=self.cur.execute.call_args.args;self.assertIn('id_comunidad=%s',sql);self.assertEqual(params,(True,99,12))
    def test_formatos_limites(self):
        for mime,n,b in [('image/jpeg',2000000,'foro-imagenes'),('video/mp4',10000000,'foro-videos')]:
            self.assertEqual(self.m['validar_archivo']({'mime':mime,'bytes':n})[0],b)
            with self.assertRaises(ValueError):self.m['validar_archivo']({'mime':mime,'bytes':n+1})
        for d in [{'mime':'text/html','bytes':5},{'mime':[],'bytes':5},{'mime':'image/png','bytes':True}]:
            with self.assertRaises(ValueError):self.m['validar_archivo'](d)
    def test_limites_personalizacion(self):
        self.assertEqual(self.m['validar_archivo']({'mime':'image/png','bytes':500000,'uso':'icono'})[0],'foro-iconos')
        self.assertEqual(self.m['validar_archivo']({'mime':'image/png','bytes':1000000,'uso':'portada'})[0],'foro-portadas')
        with self.assertRaises(ValueError):self.m['validar_archivo']({'mime':'video/mp4','bytes':10,'uso':'portada'})
    def test_personalizacion_ajena(self):
        self.cur.fetchone.return_value=None
        with self.assertRaises(ValueError):self.m['adjuntar_personalizacion'](self.cur,{'icono_archivo':str(uuid.uuid4())},7,9)
        self.assertIn('id_usuario=%s',self.cur.execute.call_args.args[0]);self.assertEqual(self.cur.execute.call_count,1)
    def test_firmas(self):
        for mime,b in [('image/jpeg',b'\xff\xd8\xff'),('image/png',b'\x89PNG\r\n\x1a\n'),('image/webp',b'RIFF0000WEBP'),('video/mp4',b'0000ftyp')]:
            self.assertTrue(self.m['firma_valida'](mime,b));self.assertFalse(self.m['firma_valida'](mime,b'<html>'))
    def test_ids_duplicados(self):
        a=str(uuid.uuid4());b=str(uuid.uuid4());self.assertEqual(self.m['validar_ids']([a,b],'multimedia'),[a,b])
        for ids,tipo in [([a,a],'multimedia'),([a,b],'video'),(['no-uuid'],'video'),([], 'video')]:
            with self.assertRaises(ValueError):self.m['validar_ids'](ids,tipo)
    def test_adjuntar_archivos_ajenos_o_no_verificados(self):
        a=str(uuid.uuid4());self.cur.fetchall.return_value=[]
        with self.assertRaises(ValueError):self.m['adjuntar_archivos'](self.cur,[a],'video',7,10)
        sql,params=self.cur.execute.call_args.args;self.assertIn("estado='verificado'",sql);self.assertIn('id_usuario=%s',sql);self.assertEqual(params,([a],7))
    def test_adjuntar_tipo_incorrecto(self):
        a=str(uuid.uuid4());self.cur.fetchall.return_value=[{'id':a,'mime':'image/png'}]
        with self.assertRaises(ValueError):self.m['adjuntar_archivos'](self.cur,[a],'video',7,10)
    def test_cuota_reserva_maximo_bucket(self):
        self.m['request']=SimpleNamespace(get_json=lambda:{'mime':'video/mp4','bytes':1});self.cur.fetchone.side_effect=[{'public':False,'file_size_limit':10000000,'allowed_mime_types':['video/mp4']},{'total_global':0,'propio':25000000}]
        self.assertEqual(self.m['reservar']()[1],409);self.con.commit.assert_not_called();self.assertIn('pg_advisory_xact_lock',self.cur.execute.call_args_list[0].args[0])
    def test_bucket_publico_rechazado(self):
        self.m['request']=SimpleNamespace(get_json=lambda:{'mime':'video/mp4','bytes':10});self.cur.fetchone.return_value={'public':True,'file_size_limit':10000000,'allowed_mime_types':['video/mp4']}
        self.assertEqual(self.m['reservar']()[1],503);self.con.commit.assert_not_called()
    def test_multimedia_y_comunidad_feed(self):
        ns=funciones('preguntas.py',{'_listar','_filtros_feed','_pregunta_publica'},{'SQL_PREGUNTA_DETALLE','ETIQUETAS','ORDENES'})
        ns.update(mysql=SimpleNamespace(connection=self.con),request=SimpleNamespace(headers={},args={'comunidad':'4','tipo':'multimedia'}))
        self.assertEqual(ns['_listar']()[1],200);sql,params=self.cur.execute.call_args.args;self.assertIn('p.id_comunidad=%s',sql);self.assertIn("p.tipo IN ('imagen','multimedia','video')",sql);self.assertEqual(params,(4,20,0))
    def test_migraciones_incrementales(self):
        for nombre in ('010_comunidades.sql','011_multimedia.sql'):
            s=(Path(__file__).resolve().parents[1]/'database/migrations'/nombre).read_text(encoding='utf-8').upper();self.assertNotIn('DROP TABLE',s);self.assertNotIn('TRUNCATE',s);self.assertIn('REVOKE ALL',s);self.assertIn('ENABLE ROW LEVEL SECURITY',s)
if __name__=='__main__':unittest.main()
