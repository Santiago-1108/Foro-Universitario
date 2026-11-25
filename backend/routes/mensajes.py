"""Mensajería privada 1 a 1. Identidad exclusiva del JWT; sin acceso administrativo especial."""
from flask import Blueprint, g, jsonify, request
from extensions import mysql
from security import token_requerido

mensajes_bp = Blueprint('mensajes', __name__, url_prefix='/mensajes')
MAX_ID = 9223372036854775807


def _id_valido(valor):
    return type(valor) is int and 0 < valor <= MAX_ID


def _par(uid, otro):
    if not _id_valido(otro) or uid == otro:
        raise ValueError('Destinatario inválido')
    return min(uid, otro), max(uid, otro)


def _pagina(args):
    try:
        limite = int(args.get('limite', '20'))
        antes = int(args['antes']) if 'antes' in args else None
    except (ValueError, TypeError):
        raise ValueError('Paginación inválida') from None
    if not 1 <= limite <= 50 or (antes is not None and not _id_valido(antes)):
        raise ValueError('Paginación inválida')
    return limite, antes


def _contenido(datos):
    texto = datos.get('contenido') if isinstance(datos, dict) else None
    if not isinstance(texto, str) or '\x00' in texto or not texto.strip() or len(texto) > 2000:
        raise ValueError('Escribe un mensaje de 1 a 2000 caracteres')
    return texto.strip()


def _mensaje(fila, uid):
    return dict(id=str(fila['id']), propio=fila['id_emisor'] == uid,
                contenido=fila['contenido'], fecha_creacion=fila['fecha_creacion'].isoformat(),
                leido=fila['fecha_lectura'] is not None)


def _contacto(cur, uid, otro, bloquear=False):
    # Las escrituras bloquean las dos filas de usuarios en orden estable. La
    # suspensión y la creación del bloqueo usan las mismas filas/orden.
    if bloquear:
        cur.execute('SELECT id,suspendido,version_sesion FROM public.usuarios WHERE id IN (%s,%s) ORDER BY id FOR UPDATE', _par(uid, otro))
        usuarios = {u['id']: u for u in cur.fetchall()}
        if (uid not in usuarios or usuarios[uid]['suspendido'] or
                usuarios[uid]['version_sesion'] != g.usuario['version_sesion']):
            return None, 401
        if otro not in usuarios or usuarios[otro]['suspendido']:
            return None, 403
    cur.execute('''SELECT id,nombre_apellido,avatar_url,suspendido FROM public.usuarios
        WHERE id=%s AND NOT public.foro_hay_bloqueo(%s,id)''', (otro, uid))
    contacto = cur.fetchone()
    if not contacto:
        return None, 404
    return contacto, None


@mensajes_bp.get('')
@token_requerido
def bandeja():
    try:
        limite, antes = _pagina(request.args)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    uid = g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute('''SELECT count(*) AS pendientes FROM public.conversaciones c
            JOIN public.mensajes m ON m.id_conversacion=c.id
            WHERE %s IN (c.usuario_a,c.usuario_b) AND m.id_emisor<>%s AND m.fecha_lectura IS NULL
              AND NOT public.foro_hay_bloqueo(c.usuario_a,c.usuario_b)''', (uid, uid))
        pendientes = cur.fetchone()['pendientes']
        if request.args.get('solo_conteo') == '1':
            return jsonify(pendientes=pendientes), 200
        sql = '''SELECT u.id AS contacto,u.nombre_apellido,u.avatar_url,u.suspendido,
            m.id,m.id_emisor,m.fecha_creacion,m.fecha_lectura,m.contenido,
            (SELECT count(*) FROM public.mensajes n WHERE n.id_conversacion=c.id
             AND n.id_emisor<>%s AND n.fecha_lectura IS NULL) AS pendientes
            FROM public.conversaciones c
            JOIN public.usuarios u ON u.id=CASE WHEN c.usuario_a=%s THEN c.usuario_b ELSE c.usuario_a END
            JOIN LATERAL (SELECT * FROM public.mensajes WHERE id_conversacion=c.id ORDER BY id DESC LIMIT 1) m ON true
            WHERE %s IN (c.usuario_a,c.usuario_b) AND NOT public.foro_hay_bloqueo(c.usuario_a,c.usuario_b)'''
        params = [uid, uid, uid]
        if antes is not None:
            sql += ' AND m.id < %s'
            params.append(antes)
        sql += ' ORDER BY m.id DESC LIMIT %s'
        cur.execute(sql, (*params, limite+1))
        filas = cur.fetchall()
    elementos = [dict(id_usuario=str(f['contacto']),nombre_apellido=f['nombre_apellido'],avatar_url=f['avatar_url'],
                      suspendido=f['suspendido'], ultimo=_mensaje(f,uid), pendientes=f['pendientes']) for f in filas[:limite]]
    return jsonify(conversaciones=elementos, pendientes=pendientes,
                   siguiente=elementos[-1]['ultimo']['id'] if len(filas)>limite else None), 200


@mensajes_bp.get('/<int:otro>')
@token_requerido
def historial(otro):
    uid = g.usuario['id']
    try:
        par = _par(uid, otro)
        limite, antes = _pagina(request.args)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    with mysql.connection.cursor() as cur:
        contacto, error = _contacto(cur, uid, otro)
        if error:
            return jsonify(error='Conversación no disponible'), error
        sql = '''SELECT m.* FROM public.mensajes m JOIN public.conversaciones c ON c.id=m.id_conversacion
            WHERE c.usuario_a=%s AND c.usuario_b=%s AND NOT public.foro_hay_bloqueo(c.usuario_a,c.usuario_b)'''
        params = list(par)
        if antes is not None:
            sql += ' AND m.id < %s'
            params.append(antes)
        sql += ' ORDER BY m.id DESC LIMIT %s'
        cur.execute(sql, (*params, limite+1))
        filas = cur.fetchall()
    mensajes = [_mensaje(f,uid) for f in filas[:limite]]
    return jsonify(contacto=dict(id=str(contacto['id']),nombre_apellido=contacto['nombre_apellido'],
                   avatar_url=contacto['avatar_url'],suspendido=contacto['suspendido']),
                   mensajes=list(reversed(mensajes)), siguiente=mensajes[-1]['id'] if len(filas)>limite else None), 200


@mensajes_bp.post('/<int:otro>')
@token_requerido
def enviar(otro):
    uid = g.usuario['id']
    try:
        par = _par(uid, otro)
        texto = _contenido(request.get_json(silent=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    with mysql.connection.cursor() as cur:
        contacto, error = _contacto(cur, uid, otro, bloquear=True)
        if error:
            return jsonify(error='Conversación no disponible'), error
        # Límite por emisor, serializado por su fila de usuario.
        cur.execute("SELECT count(*) AS cantidad FROM public.mensajes WHERE id_emisor=%s AND fecha_creacion >= clock_timestamp()-interval '1 minute'", (uid,))
        if cur.fetchone()['cantidad'] >= 30:
            return jsonify(error='Demasiados mensajes. Intenta más tarde.'), 429
        cur.execute('INSERT INTO public.conversaciones(usuario_a,usuario_b) VALUES (%s,%s) ON CONFLICT (usuario_a,usuario_b) DO NOTHING', par)
        cur.execute('SELECT id FROM public.conversaciones WHERE usuario_a=%s AND usuario_b=%s FOR UPDATE', par)
        cid = cur.fetchone()['id']
        cur.execute('''INSERT INTO public.mensajes(id_conversacion,id_emisor,contenido) VALUES (%s,%s,%s)
                       RETURNING id,id_emisor,contenido,fecha_creacion,fecha_lectura''', (cid, uid, texto))
        mensaje = _mensaje(cur.fetchone(), uid)
    mysql.connection.commit()
    return jsonify(mensaje=mensaje), 201


@mensajes_bp.put('/<int:otro>/leer')
@token_requerido
def leer(otro):
    uid = g.usuario['id']
    try:
        par = _par(uid, otro)
        datos = request.get_json(silent=True)
        hasta = datos.get('hasta') if isinstance(datos, dict) else None
        # IDs se transmiten como cadenas para evitar pérdida de precisión JS.
        if not isinstance(hasta,str) or not hasta.isascii() or not hasta.isdecimal() or len(hasta)>19 or not _id_valido(int(hasta)):
            raise ValueError('Identificador de lectura inválido')
        hasta = int(hasta)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    with mysql.connection.cursor() as cur:
        cur.execute('''SELECT c.id FROM public.conversaciones c JOIN public.mensajes m ON m.id_conversacion=c.id
            WHERE c.usuario_a=%s AND c.usuario_b=%s AND m.id=%s AND NOT public.foro_hay_bloqueo(c.usuario_a,c.usuario_b)''', (*par,hasta))
        fila = cur.fetchone()
        if not fila:
            return jsonify(error='Conversación no disponible'), 404
        cur.execute('''UPDATE public.mensajes m SET fecha_lectura=clock_timestamp()
            FROM public.conversaciones c WHERE c.id=m.id_conversacion AND c.id=%s
             AND m.id_emisor=%s AND m.id<=%s AND m.fecha_lectura IS NULL
             AND NOT public.foro_hay_bloqueo(c.usuario_a,c.usuario_b)''', (fila['id'],otro,hasta))
        cantidad = cur.rowcount
    mysql.connection.commit()
    return jsonify(marcados=cantidad), 200
