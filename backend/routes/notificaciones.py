"""Bandeja privada del usuario autenticado. Los eventos los registra PostgreSQL."""
from flask import Blueprint, g, jsonify, request
from extensions import mysql
from security import token_requerido

notificaciones_bp = Blueprint('notificaciones', __name__, url_prefix='/notificaciones')
MAX_ID = 9223372036854775807


def _parametros(args):
    solo_conteo = args.get('solo_conteo', '0')
    if solo_conteo not in ('0', '1'):
        raise ValueError('solo_conteo inválido')
    try:
        limite = int(args.get('limite', '20'))
        antes = int(args['antes']) if 'antes' in args else None
    except (ValueError, TypeError):
        raise ValueError('Paginación inválida') from None
    if not 1 <= limite <= 50 or (antes is not None and not 1 <= antes <= MAX_ID):
        raise ValueError('Paginación inválida')
    return solo_conteo == '1', limite, antes


def _publica(fila):
    # IDs como texto: conserva la precisión de BIGINT en JavaScript.
    textos = {
        'respuesta': 'respondió tu publicación.',
        'comentario': 'respondió a tu intervención.',
        'mencion': 'te mencionó en el foro.',
        'voto': 'votó positivamente tu contenido.',
        'seguidor': 'comenzó a seguirte.',
    }
    return {
        'id': str(fila['id']), 'tipo': fila['tipo'],
        'texto': f"{fila['actor']} {textos[fila['tipo']]}",
        'fecha_creacion': fila['fecha_creacion'].isoformat(),
        'leida': fila['fecha_lectura'] is not None,
        'id_pregunta': str(fila['id_pregunta']) if fila['id_pregunta'] is not None else None,
        'id_actor': str(fila['id_actor']),
    }


@notificaciones_bp.get('')
@token_requerido
def listar_notificaciones():
    try:
        solo_conteo, limite, antes = _parametros(request.args)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    uid = g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT count(*) AS pendientes FROM public.foro_notificaciones_visibles(%s) WHERE fecha_lectura IS NULL', (uid,))
        pendientes = cur.fetchone()['pendientes']
        if solo_conteo:
            return jsonify(pendientes=pendientes), 200
        sql = '''SELECT n.*, u.nombre_apellido AS actor FROM public.foro_notificaciones_visibles(%s) n
                 JOIN public.usuarios u ON u.id=n.id_actor'''
        params = [uid]
        if antes is not None:
            sql += ' WHERE n.id < %s'
            params.append(antes)
        sql += ' ORDER BY n.id DESC LIMIT %s'
        cur.execute(sql, (*params, limite + 1))
        filas = cur.fetchall()
    hay_mas = len(filas) > limite
    pagina = [_publica(f) for f in filas[:limite]]
    return jsonify(notificaciones=pagina, pendientes=pendientes,
                   siguiente=pagina[-1]['id'] if hay_mas else None), 200


@notificaciones_bp.put('/<int:id_aviso>/leer')
@token_requerido
def leer_notificacion(id_aviso):
    if not 1 <= id_aviso <= MAX_ID:
        return jsonify(error='Notificación no encontrada'), 404
    uid = g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute('''UPDATE public.notificaciones n SET fecha_lectura=COALESCE(n.fecha_lectura,now())
            WHERE n.id_destinatario=%s AND n.id=%s AND EXISTS
            (SELECT 1 FROM public.foro_notificaciones_visibles(%s) v WHERE v.id=n.id)
            RETURNING n.id''', (uid, id_aviso, uid))
        if not cur.fetchone():
            return jsonify(error='Notificación no encontrada'), 404
    mysql.connection.commit()
    return jsonify(leida=True), 200


@notificaciones_bp.put('/leer-todas')
@token_requerido
def leer_todas():
    uid = g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute('''UPDATE public.notificaciones n SET fecha_lectura=now()
            WHERE n.id_destinatario=%s AND n.fecha_lectura IS NULL AND EXISTS
            (SELECT 1 FROM public.foro_notificaciones_visibles(%s) v WHERE v.id=n.id)''', (uid, uid))
        cantidad = cur.rowcount
    mysql.connection.commit()
    return jsonify(marcadas=cantidad), 200
