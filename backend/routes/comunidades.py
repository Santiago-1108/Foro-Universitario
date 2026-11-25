"""Comunidades públicas y restringidas. Privadas deshabilitadas hasta auditar todas las lecturas."""
import re
from urllib.parse import urlsplit
from flask import Blueprint, g, jsonify, request
from extensions import mysql
from security import token_requerido, _usuario_desde_token
from routes.multimedia import adjuntar_personalizacion

comunidades_bp = Blueprint('comunidades', __name__, url_prefix='/comunidades')

def validar_comunidad(d):
    if not isinstance(d,dict): raise ValueError('Datos inválidos')
    out={}
    for k,minimo,maximo in [('nombre',3,60),('slug',3,40),('descripcion',1,500),('normas',0,2000),('icono_url',0,2048),('portada_url',0,2048)]:
        v=d.get(k,'')
        if not isinstance(v,str) or '\x00' in v or not minimo<=len(v.strip())<=maximo: raise ValueError(k+' inválido')
        v=v.strip()
        if k.endswith('_url') and v:
            u=urlsplit(v)
            if u.scheme!='https' or not u.hostname or u.username or u.password or any(c.isspace() or c=='\\' for c in v): raise ValueError('URL HTTPS inválida')
        out[k]=v
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,39}',out['slug']): raise ValueError('Identificador inválido')
    if d.get('tipo') not in ('publica','restringida'): raise ValueError('Las comunidades privadas aún no están habilitadas')
    if type(d.get('id_categoria')) is not int or not 0<d['id_categoria']<=9223372036854775807: raise ValueError('Temática inválida')
    return dict(out,tipo=d['tipo'],id_categoria=d['id_categoria'])

BASE='''SELECT c.*,cat.nombre AS tematica, (SELECT count(*) FROM miembros_comunidades m WHERE m.id_comunidad=c.id AND m.aprobado) AS miembros,
 (SELECT m.rol FROM miembros_comunidades m WHERE m.id_comunidad=c.id AND m.id_usuario=%s AND m.aprobado) AS mi_rol,
 EXISTS(SELECT 1 FROM miembros_comunidades m WHERE m.id_comunidad=c.id AND m.id_usuario=%s AND NOT m.aprobado) AS pendiente
 FROM comunidades c JOIN categorias cat ON cat.id=c.id_categoria'''

@comunidades_bp.get('')
def listar():
    uid=None
    if request.headers.get('Authorization') or request.args.get('mias')=='1':
        u,e=_usuario_desde_token()
        if e:return e
        uid=u['id']
    q=request.args.get('q','').strip()
    try: offset=int(request.args.get('offset','0'))
    except ValueError:return jsonify(error='Paginación inválida'),400
    if len(q)>120 or '\x00' in q or not 0<=offset<=100000:return jsonify(error='Filtros inválidos'),400
    sql=BASE+' WHERE (strpos(lower(c.nombre),lower(%s))>0 OR strpos(lower(c.descripcion),lower(%s))>0 OR %s=\'\')'
    args=[uid,uid,q,q,q]
    if request.args.get('mias')=='1':sql+=' AND EXISTS(SELECT 1 FROM miembros_comunidades m WHERE m.id_comunidad=c.id AND m.id_usuario=%s AND m.aprobado)';args.append(uid)
    with mysql.connection.cursor() as cur:
        cur.execute(sql+' ORDER BY c.nombre,c.id LIMIT 21 OFFSET %s',(*args,offset));return jsonify(cur.fetchall())

@comunidades_bp.post('')
@token_requerido
def crear():
    try:d=validar_comunidad(request.get_json())
    except ValueError as e:return jsonify(error=str(e)),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT id FROM categorias WHERE id=%s',(d['id_categoria'],))
        if not cur.fetchone():return jsonify(error='Temática no encontrada'),404
        cur.execute('''INSERT INTO comunidades(id_categoria,id_propietario,nombre,slug,descripcion,tipo,normas,icono_url,portada_url) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',(d['id_categoria'],g.usuario['id'],d['nombre'],d['slug'],d['descripcion'],d['tipo'],d['normas'],d['icono_url'] or None,d['portada_url'] or None))
        cid=cur.fetchone()['id'];cur.execute("INSERT INTO miembros_comunidades VALUES(%s,%s,'propietario',true,now())",(cid,g.usuario['id']))
        try:adjuntar_personalizacion(cur,request.get_json(),g.usuario['id'],cid)
        except ValueError as e:mysql.connection.rollback();return jsonify(error=str(e)),400
    mysql.connection.commit();return jsonify(id=cid,slug=d['slug']),201

@comunidades_bp.get('/<slug>')
def detalle(slug):
    uid=None
    if request.headers.get('Authorization'):
        u,e=_usuario_desde_token()
        if e:return e
        uid=u['id']
    with mysql.connection.cursor() as cur:
        cur.execute(BASE+' WHERE c.slug=%s',(uid,uid,slug));c=cur.fetchone()
        if not c:return jsonify(error='Comunidad no encontrada'),404
        cur.execute("SELECT u.id,u.nombre_apellido,m.rol FROM miembros_comunidades m JOIN usuarios u ON u.id=m.id_usuario WHERE m.id_comunidad=%s AND m.aprobado AND m.rol IN ('propietario','moderador') ORDER BY m.rol,u.id",(c['id'],));c['moderadores']=cur.fetchall()
        return jsonify(c)

@comunidades_bp.put('/<int:cid>/membresia')
@token_requerido
def membresia(cid):
    d=request.get_json();unirse=d.get('unirse')
    if type(unirse) is not bool:return jsonify(error='unirse debe ser booleano'),400
    uid=g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT * FROM comunidades WHERE id=%s FOR UPDATE',(cid,));c=cur.fetchone()
        if not c:return jsonify(error='Comunidad no encontrada'),404
        if c['id_propietario']==uid and not unirse:return jsonify(error='El propietario no puede abandonar su comunidad'),409
        if unirse:cur.execute("INSERT INTO miembros_comunidades(id_comunidad,id_usuario,rol,aprobado) VALUES(%s,%s,'miembro',%s) ON CONFLICT DO NOTHING",(cid,uid,c['tipo']=='publica'))
        else:cur.execute('DELETE FROM miembros_comunidades WHERE id_comunidad=%s AND id_usuario=%s AND rol<>\'propietario\'',(cid,uid))
    mysql.connection.commit();return jsonify(ok=True)

def _gestor(cur,cid,solo_propietario=False):
    cur.execute('SELECT c.*,m.rol AS mi_rol FROM comunidades c JOIN miembros_comunidades m ON m.id_comunidad=c.id WHERE c.id=%s AND m.id_usuario=%s AND m.aprobado FOR UPDATE OF c',(cid,g.usuario['id']));c=cur.fetchone()
    return c if c and c['mi_rol'] in (('propietario',) if solo_propietario else ('propietario','moderador')) else None

@comunidades_bp.put('/<int:cid>')
@token_requerido
def editar(cid):
    with mysql.connection.cursor() as cur:
        c=_gestor(cur,cid,True)
        if not c:return jsonify(error='Solo el propietario puede editar'),403
        d=request.get_json()
        if any(k in d for k in ('tipo','id_categoria','slug','id_propietario')):return jsonify(error='Tipo, temática e identificador no se pueden cambiar'),400
        try:v=validar_comunidad({**c,**d,'icono_url':d.get('icono_url',c['icono_url'] or ''),'portada_url':d.get('portada_url',c['portada_url'] or '')})
        except ValueError as e:return jsonify(error=str(e)),400
        cur.execute('UPDATE comunidades SET nombre=%s,descripcion=%s,normas=%s,icono_url=%s,portada_url=%s WHERE id=%s',(v['nombre'],v['descripcion'],v['normas'],v['icono_url'] or None,v['portada_url'] or None,cid))
        try:adjuntar_personalizacion(cur,d,g.usuario['id'],cid)
        except ValueError as e:mysql.connection.rollback();return jsonify(error=str(e)),400
    mysql.connection.commit();return jsonify(ok=True)

@comunidades_bp.get('/<int:cid>/miembros')
@token_requerido
def miembros(cid):
    with mysql.connection.cursor() as cur:
        if not _gestor(cur,cid,True):return jsonify(error='No autorizado'),403
        cur.execute('SELECT m.id_usuario,m.rol,m.aprobado,u.nombre_apellido FROM miembros_comunidades m JOIN usuarios u ON u.id=m.id_usuario WHERE m.id_comunidad=%s ORDER BY m.aprobado,u.id',(cid,));return jsonify(cur.fetchall())

@comunidades_bp.put('/<int:cid>/miembros/<int:uid>')
@token_requerido
def gestionar_miembro(cid,uid):
    accion=request.get_json().get('accion')
    if accion not in ('aprobar','expulsar','moderador','miembro'):return jsonify(error='Acción inválida'),400
    with mysql.connection.cursor() as cur:
        c=_gestor(cur,cid,True)
        if not c or uid==c['id_propietario']:return jsonify(error='No autorizado'),403
        if accion=='expulsar':cur.execute('DELETE FROM miembros_comunidades WHERE id_comunidad=%s AND id_usuario=%s',(cid,uid))
        elif accion=='aprobar':cur.execute('UPDATE miembros_comunidades SET aprobado=true WHERE id_comunidad=%s AND id_usuario=%s',(cid,uid))
        else:cur.execute('UPDATE miembros_comunidades SET rol=%s WHERE id_comunidad=%s AND id_usuario=%s AND aprobado',(accion,cid,uid))
        if not cur.rowcount:return jsonify(error='Miembro no encontrado'),404
    mysql.connection.commit();return jsonify(ok=True)

@comunidades_bp.put('/<int:cid>/preguntas/<int:pid>')
@token_requerido
def moderar(cid,pid):
    d=request.get_json();accion=d.get('accion')
    if accion not in ('fijada','cerrada','eliminar') or (accion!='eliminar' and type(d.get('valor')) is not bool):return jsonify(error='Acción inválida'),400
    with mysql.connection.cursor() as cur:
        if not _gestor(cur,cid):return jsonify(error='No autorizado'),403
        if accion=='eliminar':cur.execute('UPDATE preguntas SET fecha_eliminacion=now() WHERE id=%s AND id_comunidad=%s AND fecha_eliminacion IS NULL',(pid,cid))
        else:cur.execute(f'UPDATE preguntas SET {accion}=%s WHERE id=%s AND id_comunidad=%s AND fecha_eliminacion IS NULL',(d['valor'],pid,cid))
        if not cur.rowcount:return jsonify(error='Publicación no encontrada'),404
    mysql.connection.commit();return jsonify(ok=True)
