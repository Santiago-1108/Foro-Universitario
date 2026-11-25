"""Prueba de integración REAL contra dispatcher local y una BD de pruebas.
No ejecutar contra producción. Crea registros de prueba persistentes.
"""
import argparse
import json
import secrets
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='http://127.0.0.1:8000')
parser.add_argument('--confirmar-base-de-pruebas', action='store_true', required=True)
args = parser.parse_args()
if args.base not in ('http://127.0.0.1:8000', 'http://localhost:8000'):
    parser.error('Solo se admite el dispatcher local en puerto 8000')


def api(servicio, ruta, metodo='GET', datos=None, token=None, esperado=200):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(f'{args.base}/api/{servicio}{ruta}', data=json.dumps(datos).encode() if datos is not None else None,
                  method=metodo, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            estado, cuerpo = resp.status, resp.read()
    except HTTPError as err:
        estado, cuerpo = err.code, err.read()
    if estado != esperado:
        raise RuntimeError(f'{metodo} {servicio}{ruta}: HTTP {estado}, esperado {esperado}. {cuerpo[:400]!r}')
    print(f'OK {estado}: {metodo} {servicio}{ruta}')
    return json.loads(cuerpo)


def crear_usuario(nombre):
    correo = f'prueba-{secrets.token_hex(8)}@example.invalid'
    clave = secrets.token_urlsafe(20)
    registro = api('usuarios','/auth/registro','POST',dict(nombre_apellido=nombre,correo=correo,password=clave),esperado=201)
    sesion = api('usuarios','/auth/login','POST',dict(correo=correo,password=clave))
    return registro['id'],sesion['token']


cats = api('foro','/categorias')
if not cats:
    raise RuntimeError('Crea primero una categoría en la BD de pruebas')
a, ta = crear_usuario('Prueba integración A')
b, tb = crear_usuario('Prueba integración B')
c, tc = crear_usuario('Prueba integración C')
api('usuarios','/usuarios/yo',token=ta)
api('usuarios','/moderacion/estadisticas',token=ta,esperado=403)
payload=dict(id_categoria=cats[0]['id'],titulo='Prueba integración '+secrets.token_hex(4),contenido='Contenido de prueba',tipo='encuesta',opciones_encuesta=['A','B'],etiqueta='duda')
api('foro','/preguntas/borrador','PUT',{'datos':payload},ta)
assert api('foro','/preguntas/borrador',token=ta)['titulo']==payload['titulo']
assert api('foro','/preguntas/borrador',token=tb) is None
p=api('foro','/preguntas','POST',payload,ta,201)['id']
api('foro',f'/preguntas/{p}/encuesta','PUT',{'opcion':1},tb)
assert api('foro',f'/preguntas/{p}/encuesta',token=tb)['mi_opcion']==1
r=api('interacciones','/respuestas','POST',{'id_pregunta':p,'contenido':'Respuesta de prueba'},tb,201)['id']
co=api('interacciones','/comentarios','POST',{'id_respuesta':r,'contenido':'Comentario raíz'},ta,201)['id']
api('interacciones','/comentarios','POST',{'id_respuesta':r,'id_comentario_padre':co,'contenido':'Comentario anidado'},tb,201)
api('foro',f'/preguntas/{p}/aceptar','PUT',{'id_respuesta':r},ta)
for valor in (1,1,-1,0,1):
    api('interacciones','/votos','POST',{'id_pregunta':p,'voto':valor},tb)
assert api('interacciones',f'/votos/pregunta/{p}',token=tb)['total_votos']==1
# Regresiones de la auditoría: contrato real con PostgreSQL y JWT.
for orden in ('para_ti','reciente','antiguo','popular','tendencias','relevancia'):
    api('foro',f'/preguntas?orden={orden}&limite=21&offset=0',token=tb)
api('foro','/preguntas?orden=para_ti&limite=21&offset=0')
api('foro','/preguntas?orden=desconocido',esperado=400)
api('foro','/preguntas?vista=historial',esperado=401)
assert api('foro','/preguntas?vista=historial&orden=reciente&limite=21',token=tb)==[]
api('foro',f'/preguntas/{p}/visita','POST',{},tb)
assert any(x['id']==p for x in api('foro','/preguntas?vista=historial&orden=reciente&limite=21',token=tb))
assert api('foro','/preguntas?vista=historial',token=tc)==[]
# Borrar únicamente el historial de esta cuenta de prueba recién creada.
api('foro','/preguntas/historial','DELETE',token=tb)
assert api('foro','/preguntas?vista=historial',token=tb)==[]
api('interacciones','/votos','POST',{'id_respuesta':r,'voto':1},ta)
api('interacciones','/votos','POST',{'id_pregunta':p,'voto':-1},tc)
api('interacciones','/votos','POST',{'id_respuesta':r,'voto':-1},tc)
for signo,token,tipo,objeto in ((1,tb,'publicacion',p),(1,ta,'respuesta',r),(-1,tc,'publicacion',p),(-1,tc,'respuesta',r)):
    votos=api('usuarios',f'/usuarios/perfil/votos?signo={signo}&tipo={tipo}&offset=0',token=token)['actividad']
    assert any(x['id']==objeto and x['tipo']==tipo for x in votos)
    assert all(x['tipo']==tipo for x in votos)
api('usuarios','/usuarios/perfil/votos?signo=1&tipo=respuesta',esperado=401)
for tipo,token,uid,objeto in (('publicacion',ta,a,p),('respuesta',tb,b,r),('comentario',ta,a,co)):
    filas=api('usuarios',f'/usuarios/{uid}/actividad?tipo={tipo}&offset=0',token=token)['actividad']
    assert any(x['id']==objeto for x in filas) and all(x['tipo']==tipo for x in filas)
api('usuarios',f'/usuarios/{a}/seguir','PUT',{'seguir':True},tb)
assert any(x['id']==p for x in api('foro','/preguntas?vista=personalizado&orden=reciente&limite=21',token=tb))
api('foro',f'/preguntas/{p}/guardar','PUT',{'activo':True},tb)
assert any(x['id']==p for x in api('foro','/preguntas?vista=guardadas',token=tb))
assert api('usuarios','/notificaciones?solo_conteo=1',token=ta)['pendientes']>0
api('usuarios','/notificaciones/leer-todas','PUT',{},ta)
assert api('usuarios','/notificaciones?solo_conteo=1',token=ta)['pendientes']==0
m=api('usuarios',f'/mensajes/{a}','POST',{'contenido':'Mensaje de prueba'},tb,201)['mensaje']
assert any(x['id']==m['id'] for x in api('usuarios',f'/mensajes/{b}',token=ta)['mensajes'])
assert api('usuarios',f'/mensajes/{b}',token=tc)['mensajes']==[]
api('usuarios',f'/mensajes/{b}/leer','PUT',{'hasta':m['id']},ta)
api('usuarios','/moderacion/reportes','POST',{'tipo':'pregunta','id_objeto':p,'motivo':'otro','detalle':'Prueba de integración'},tb,201)
api('usuarios',f'/usuarios/{b}/bloquear','PUT',{'activo':True},ta)
api('usuarios',f'/mensajes/{a}','POST',{'contenido':'Bloqueado'},tb,404)
api('usuarios',f'/usuarios/{b}/bloquear','PUT',{'activo':False},ta)
api('foro',f'/preguntas/{p}','DELETE',token=ta)
api('foro',f'/preguntas/{p}',esperado=404)
print('Prueba HTTP completada. Los registros se conservan en la base de pruebas.')
