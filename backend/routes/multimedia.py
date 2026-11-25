"""Cargas directas firmadas; Flask solo autoriza, verifica metadatos y cabecera corta."""
import json, os, uuid
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from flask import Blueprint, g, jsonify, request
from extensions import mysql
from security import token_requerido, _usuario_desde_token

multimedia_bp=Blueprint('multimedia',__name__,url_prefix='/multimedia')
MAX_USUARIO_BYTES=30000000
MAX_GLOBAL_BYTES=800000000
TIPOS={'image/jpeg':('foro-imagenes','jpg',2000000),'image/png':('foro-imagenes','png',2000000),'image/webp':('foro-imagenes','webp',2000000),'video/mp4':('foro-videos','mp4',10000000)}

class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def _storage_config():
    url=os.environ.get('SUPABASE_URL','').strip().rstrip('/'); clave=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','').strip()
    u=urlsplit(url)
    if not clave or u.scheme!='https' or not u.hostname or not u.hostname.endswith('.supabase.co') or u.netloc!=u.hostname or u.path or u.query or u.fragment:raise RuntimeError('Storage no configurado')
    if clave.startswith(('sb_publishable_', 'sb_anon_')):raise RuntimeError('Storage requiere clave privada')
    return url+'/storage/v1',clave

def _storage_headers(clave):
    headers={'apikey':clave,'Content-Type':'application/json'}
    if not clave.startswith('sb_secret_'):
        headers['Authorization']='Bearer '+clave
    return headers

def _storage(method,path,data=None,fragmento=False):
    base,clave=_storage_config()
    headers=_storage_headers(clave)
    if fragmento:headers['Range']='bytes=0-31'
    req=Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
    with build_opener(SinRedireccion()).open(req,timeout=8) as r:
        if fragmento:return r.read(32)
        return json.loads(r.read(65536))

def _url_firmada(path,resultado,clave):
    base,_=_storage_config(); value=resultado.get(clave,'')
    if not isinstance(value,str) or not value.startswith(path+'?'):raise RuntimeError('Respuesta de Storage inválida')
    return base+value

def validar_archivo(d):
    if not isinstance(d,dict) or not isinstance(d.get('mime'),str) or d.get('mime') not in TIPOS:raise ValueError('Formato no admitido')
    b,ext,tope=TIPOS[d['mime']];n=d.get('bytes')
    uso=d.get('uso','publicacion')
    if uso not in ('publicacion','icono','portada'):raise ValueError('Uso inválido')
    if uso!='publicacion':
        if d['mime']=='video/mp4':raise ValueError('Solo se permiten imágenes de comunidad')
        b,tope=('foro-iconos',500000) if uso=='icono' else ('foro-portadas',1000000)
    if type(n) is not int or not 0<n<=tope:raise ValueError('Tamaño inválido')
    return b,ext,tope

def validar_ids(ids,tipo):
    if not isinstance(ids,list) or len(ids)>(1 if tipo=='video' else 3) or not ids:raise ValueError('Cantidad de archivos inválida')
    if any(not isinstance(i,str) for i in ids):raise ValueError('Identificador inválido')
    try:val=[str(uuid.UUID(i)) for i in ids]
    except (ValueError,TypeError):raise ValueError('Identificador inválido')
    if len(set(val))!=len(val):raise ValueError('Archivos duplicados')
    return val

def firma_valida(mime,b):
    return (mime=='image/jpeg' and b.startswith(b'\xff\xd8\xff') or mime=='image/png' and b.startswith(b'\x89PNG\r\n\x1a\n') or mime=='image/webp' and b[:4]==b'RIFF' and b[8:12]==b'WEBP' or mime=='video/mp4' and b[4:8]==b'ftyp')

def _error_storage(motivo='Storage no disponible. Revisa la configuración de Supabase.'):
    return jsonify(error=motivo),503

def _fallo_storage(e):
    # Nunca devolver el cuerpo de la respuesta, URL firmada ni credenciales.
    if isinstance(e,HTTPError):
        if e.code in (401,403):return _error_storage(f'Supabase Storage rechazó la autorización (HTTP {e.code}). Revisa la clave privada y el proyecto.')
        return _error_storage(f'Supabase Storage respondió HTTP {e.code}. Revisa el bucket y los registros de Storage.')
    if isinstance(e,(URLError,OSError)):return _error_storage('No se pudo conectar a Supabase Storage.')
    return _error_storage('Storage devolvió una respuesta inválida o la configuración no es válida.')

@multimedia_bp.post('/reservar')
@token_requerido
def reservar():
    d=request.get_json()
    try:bucket,ext,maximo=validar_archivo(d);_storage_config()
    except ValueError as e:return jsonify(error=str(e)),400
    except RuntimeError:return _error_storage('Configura SUPABASE_URL y una clave privada SUPABASE_SERVICE_ROLE_KEY en la terminal del foro (5001).')
    uid=g.usuario['id'];aid=str(uuid.uuid4());ruta=f'{uid}/{aid}.{ext}'
    with mysql.connection.cursor() as cur:
        # Reserva por máximo físico del bucket, no por tamaño declarado. Serializa todas las reservas.
        cur.execute('SELECT pg_advisory_xact_lock(70621101)')
        cur.execute('SELECT public,file_size_limit,allowed_mime_types FROM storage.buckets WHERE id=%s',(bucket,));b=cur.fetchone()
        tipos={'video/mp4'} if bucket=='foro-videos' else {'image/jpeg','image/png','image/webp'}
        # El panel puede expresar MB/KB en base 1024. La cuota cuenta el máximo físico
        # posible; el tamaño aceptado por la aplicación y la restricción SQL siguen en bytes decimales.
        fisico={'foro-iconos':500*1024,'foro-portadas':1024**2,'foro-imagenes':2*1024**2,'foro-videos':10*1024**2}[bucket]
        if not b:return _error_storage(f'Falta el bucket {bucket}.')
        if b['public']:return _error_storage(f'El bucket {bucket} debe ser privado.')
        if not isinstance(b['file_size_limit'],int) or not 0<b['file_size_limit']<=fisico:return _error_storage(f'El límite del bucket {bucket} debe ser mayor que cero y como máximo {fisico} bytes.')
        if set(b['allowed_mime_types'] or [])!=tipos:return _error_storage(f'Revisa los formatos MIME exactos del bucket {bucket}.')
        if d['bytes']>b['file_size_limit']:return jsonify(error='El archivo supera el límite configurado del bucket'),400
        cur.execute("""SELECT COALESCE(sum(maximo_fisico),0) AS total_global, COALESCE(sum(maximo_fisico) FILTER(WHERE id_usuario=%s),0) AS propio FROM (SELECT id_usuario,CASE bucket WHEN 'foro-iconos' THEN 512000 WHEN 'foro-portadas' THEN 1048576 WHEN 'foro-imagenes' THEN 2097152 WHEN 'foro-videos' THEN 10485760 ELSE bytes_reservados END AS maximo_fisico FROM archivos_foro WHERE estado<>'eliminado') reservas""",(uid,));cuota=cur.fetchone()
        if cuota['total_global']+fisico>MAX_GLOBAL_BYTES or cuota['propio']+fisico>MAX_USUARIO_BYTES:return jsonify(error='Cuota de almacenamiento agotada'),409
        cur.execute("INSERT INTO archivos_foro(id,id_usuario,bucket,ruta,mime,bytes_reservados,expira) VALUES(%s,%s,%s,%s,%s,%s,now()+interval '3 hours')",(aid,uid,bucket,ruta,d['mime'],maximo))
    # Commit antes de firmar: si la red falla, la reserva permanece contabilizada.
    mysql.connection.commit()
    path=f'/object/upload/sign/{bucket}/{ruta}'
    try:url=_url_firmada(path,_storage('POST',path,{}),'url')
    except (URLError,OSError,ValueError,RuntimeError) as e:return _fallo_storage(e)
    return jsonify(id=aid,url=url),201

@multimedia_bp.put('/<uuid:aid>/verificar')
@token_requerido
def verificar(aid):
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT * FROM archivos_foro WHERE id=%s AND id_usuario=%s AND estado IN ('pendiente','verificado') AND expira>now() FOR UPDATE",(str(aid),g.usuario['id']));a=cur.fetchone()
        if not a:return jsonify(error='Reserva no disponible'),404
        cur.execute('SELECT metadata FROM storage.objects WHERE bucket_id=%s AND name=%s',(a['bucket'],a['ruta']));obj=cur.fetchone()
        if not obj:return jsonify(error='El archivo aún no existe en Storage'),409
        m=obj['metadata'] or {};n=m.get('size');mime=m.get('mimetype')
        if type(n) is not int or not 0<n<=a['bytes_reservados'] or mime!=a['mime']:return jsonify(error='El archivo no cumple tamaño o formato'),422
        try:head=_storage('GET',f"/object/authenticated/{a['bucket']}/{a['ruta']}",fragmento=True)
        except (URLError,OSError,ValueError,RuntimeError) as e:return _fallo_storage(e)
        if not firma_valida(mime,head):return jsonify(error='Firma de archivo no admitida'),422
        cur.execute("UPDATE archivos_foro SET estado='verificado',bytes_reales=%s WHERE id=%s",(n,str(aid)))
    mysql.connection.commit();return jsonify(id=str(aid),mime=mime,bytes=n)

def adjuntar_archivos(cur,ids,tipo,uid,pid):
    ids=validar_ids(ids,tipo)
    cur.execute("SELECT id::text AS id,mime FROM archivos_foro WHERE id=ANY(%s::uuid[]) AND id_usuario=%s AND estado='verificado' AND expira>now() AND bucket IN ('foro-imagenes','foro-videos') ORDER BY id FOR UPDATE",(ids,uid));rows=cur.fetchall()
    if len(rows)!=len(ids) or any((r['mime']=='video/mp4')!=(tipo=='video') for r in rows):raise ValueError('Archivos no disponibles o de tipo incorrecto')
    cur.execute("UPDATE archivos_foro SET id_pregunta=%s,estado='adjunto' WHERE id=ANY(%s::uuid[])",(pid,ids))

@multimedia_bp.get('/publicaciones/<int:pid>')
def archivos_publicacion(pid):
    uid=None
    if request.headers.get('Authorization'):
        u,e=_usuario_desde_token()
        if e:return e
        uid=u['id']
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT a.id,a.bucket,a.ruta,a.mime FROM archivos_foro a JOIN preguntas p ON p.id=a.id_pregunta WHERE p.id=%s AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND a.estado='adjunto' ORDER BY a.fecha_creacion,a.id",(pid,uid));rows=cur.fetchall()
    out=[]
    try:
        for a in rows:
            path=f"/object/sign/{a['bucket']}/{a['ruta']}"
            url=_url_firmada(path,_storage('POST',path,{'expiresIn':300}),'signedURL')
            out.append(dict(id=str(a['id']),mime=a['mime'],url=url))
    except (URLError,OSError,ValueError,RuntimeError) as e:return _fallo_storage(e)
    return jsonify(out),200,{'Cache-Control':'private, no-store'}

@multimedia_bp.delete('/<uuid:aid>')
@token_requerido
def cancelar(aid):
    with mysql.connection.cursor() as cur:
        cur.execute("UPDATE archivos_foro SET estado='cancelado' WHERE id=%s AND id_usuario=%s AND estado IN ('pendiente','verificado')",(str(aid),g.usuario['id']))
        if not cur.rowcount:return jsonify(error='Reserva no disponible'),404
    mysql.connection.commit();return jsonify(ok=True)

@multimedia_bp.post('/limpiar')
@token_requerido
def limpiar():
    # No liberar la cuota mientras el token pudiera volver a cargar el objeto.
    uid=g.usuario['id'];n=0
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT a.* FROM archivos_foro a LEFT JOIN preguntas p ON p.id=a.id_pregunta WHERE a.id_usuario=%s AND a.expira<now() AND a.estado<>'eliminado' AND ((a.id_pregunta IS NULL AND a.id_comunidad IS NULL) OR p.fecha_eliminacion IS NOT NULL) ORDER BY a.fecha_creacion LIMIT 3 FOR UPDATE OF a",(uid,));rows=cur.fetchall()
        for a in rows:
            try:
                _storage('DELETE',f"/object/{a['bucket']}",{'prefixes':[a['ruta']]})
            except (URLError,OSError,ValueError,RuntimeError) as e:return _fallo_storage(e)
            cur.execute('SELECT 1 FROM storage.objects WHERE bucket_id=%s AND name=%s',(a['bucket'],a['ruta']))
            if cur.fetchone():return jsonify(error='No se confirmó la eliminación'),503
            cur.execute("UPDATE archivos_foro SET estado='eliminado' WHERE id=%s",(str(a['id']),));n+=1
    mysql.connection.commit();return jsonify(eliminados=n)


def adjuntar_personalizacion(cur,datos,uid,cid):
    for campo,bucket in [('icono_archivo','foro-iconos'),('portada_archivo','foro-portadas')]:
        if campo not in datos:continue
        aid=datos[campo]
        if aid is not None:
            aid=validar_ids([aid],'video')[0] # exactamente un UUID; el bucket determina el tipo real
            cur.execute("SELECT id FROM archivos_foro WHERE id=%s AND id_usuario=%s AND bucket=%s AND estado='verificado' AND expira>now() FOR UPDATE",(aid,uid,bucket))
            if not cur.fetchone():raise ValueError('Archivo de comunidad no disponible')
        cur.execute("UPDATE archivos_foro SET estado='cancelado',id_comunidad=NULL WHERE id_comunidad=%s AND bucket=%s AND estado='adjunto'",(cid,bucket))
        if aid is not None:
            cur.execute("UPDATE archivos_foro SET estado='adjunto',id_comunidad=%s WHERE id=%s",(cid,aid))

@multimedia_bp.get('/comunidades/<int:cid>')
def archivos_comunidad(cid):
    # Solo existen comunidades de lectura pública. No habilitar este endpoint para privadas sin autorización.
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT a.bucket,a.ruta FROM archivos_foro a JOIN comunidades c ON c.id=a.id_comunidad WHERE c.id=%s AND c.tipo IN ('publica','restringida') AND a.estado='adjunto'",(cid,));rows=cur.fetchall()
    out={}
    try:
        for a in rows:
            path=f"/object/sign/{a['bucket']}/{a['ruta']}"
            out['icono' if a['bucket']=='foro-iconos' else 'portada']=_url_firmada(path,_storage('POST',path,{'expiresIn':300}),'signedURL')
    except (URLError,OSError,ValueError,RuntimeError) as e:return _fallo_storage(e)
    return jsonify(out),200,{'Cache-Control':'private, no-store'}
