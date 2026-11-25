"""Regresión aislada: configuración del Storage, sin conexión a Supabase."""
import unittest, os, uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from test_navegacion import funciones

class StorageConfiguracion(unittest.TestCase):
    def setUp(self):
        self.ns=funciones('multimedia.py',{'_storage_config','_storage_headers','_error_storage','_fallo_storage','validar_archivo','reservar'}, {'TIPOS','MAX_USUARIO_BYTES','MAX_GLOBAL_BYTES'})
        self.cur=MagicMock(); self.cur.__enter__.return_value=self.cur
        self.con=MagicMock(); self.con.cursor.return_value=self.cur
        self.ns.update(os=os,uuid=uuid,HTTPError=HTTPError,URLError=URLError,mysql=SimpleNamespace(connection=self.con),g=SimpleNamespace(usuario={'id':7}),_storage=lambda *a:{},_url_firmada=lambda *a:'https://example.invalid/firmada')
    def test_secret_solo_apikey(self):
        h=self.ns['_storage_headers']('sb_secret_ejemplo');self.assertEqual(h['apikey'],'sb_secret_ejemplo');self.assertNotIn('Authorization',h)
    def test_legacy_bearer(self):
        h=self.ns['_storage_headers']('eyJ.ejemplo.firma');self.assertEqual(h['Authorization'],'Bearer eyJ.ejemplo.firma')
    def test_config_rechaza_publica(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'https://ejemplo.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'sb_publishable_ejemplo'}):
            with self.assertRaises(RuntimeError):self.ns['_storage_config']()
    def test_config_nueva(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'https://ejemplo.supabase.co/','SUPABASE_SERVICE_ROLE_KEY':'sb_secret_ejemplo'}):
            self.assertEqual(self.ns['_storage_config'](),('https://ejemplo.supabase.co/storage/v1','sb_secret_ejemplo'))
    def reserva(self, uso='icono', limite=512000, cuota=0, mime='image/png', n=100):
        self.ns['_storage_config']=lambda:None
        self.ns['request']=SimpleNamespace(get_json=lambda:{'uso':uso,'mime':mime,'bytes':n})
        tipos=['video/mp4'] if mime=='video/mp4' else ['image/png','image/jpeg','image/webp']
        self.cur.fetchone.side_effect=[{'public':False,'file_size_limit':limite,'allowed_mime_types':tipos},{'total_global':cuota,'propio':cuota}]
        return self.ns['reservar']()
    def test_bucket_binario(self):
        self.assertEqual(self.reserva()[1],201)
        self.assertIn('512000',self.cur.execute.call_args_list[2].args[0]);self.assertEqual(self.cur.execute.call_args.args[1][-1],500000)
    def test_portada_binaria(self):self.assertEqual(self.reserva('portada',1048576)[1],201)
    def test_limite_decimal(self):self.assertEqual(self.reserva(n=500001)[1],400)
    def test_limite_fisico_excesivo(self):self.assertEqual(self.reserva(limite=512001)[1],503)
    def test_cuota_conservadora(self):self.assertEqual(self.reserva(cuota=29499000)[1],409)
    def test_error_seguro(self):
        msg,status=self.ns['_fallo_storage'](HTTPError('https://example.invalid/?token=secreto',401,'secreto',None,None));self.assertEqual(status,503);self.assertIn('401',msg['error']);self.assertNotIn('secreto',msg['error'])
