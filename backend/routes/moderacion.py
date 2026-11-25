"""Reportes privados y administración; no expone reportantes al público."""
from flask import Blueprint, g, jsonify, request
from extensions import mysql
from security import solo_admin, token_requerido

moderacion_bp = Blueprint('moderacion', __name__, url_prefix='/moderacion')
MOTIVOS = ('spam', 'acoso', 'contenido_inapropiado', 'otro')
DESTINOS = {
    'usuario': 'SELECT id,id AS autor FROM usuarios WHERE id=%s',
    'pregunta': 'SELECT id,id_usuario AS autor FROM preguntas WHERE id=%s AND fecha_eliminacion IS NULL',
    'respuesta': 'SELECT r.id,r.id_usuario AS autor FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta WHERE r.id=%s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL',
    'comentario': 'SELECT c.id,c.id_usuario AS autor FROM comentarios c JOIN respuestas r ON r.id=c.id_respuesta JOIN preguntas p ON p.id=r.id_pregunta WHERE c.id=%s AND c.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL',
}


def _texto(valor):
    if not isinstance(valor, str) or len(valor)>500 or '\x00' in valor:
        raise ValueError('Detalle inválido (máximo 500 caracteres)')
    return valor.strip()


def _id(valor):
    if type(valor) is not int or not 0<valor<=9223372036854775807:
        raise ValueError('Identificador inválido')
    return valor


def _pagina(args):
    limite=int(args.get('limite',30)); antes=int(args.get('antes',9223372036854775807))
    if not 1<=limite<=100 or not 0<antes<=9223372036854775807:
        raise ValueError('Paginación inválida')
    return limite,antes


def registrar_accion(cur, accion, tipo, destino, detalle=''):
    cur.execute('INSERT INTO historial_moderacion(id_admin,accion,tipo,id_objeto,detalle) VALUES (%s,%s,%s,%s,%s)',
                (g.usuario['id'],accion,tipo,destino,detalle))


@moderacion_bp.route('/reportes', methods=['POST'])
@token_requerido
def crear_reporte():
    datos=request.get_json()
    tipo=datos.get('tipo'); motivo=datos.get('motivo')
    if not isinstance(tipo,str) or tipo not in DESTINOS or motivo not in MOTIVOS:
        return jsonify(error='Tipo o motivo inválido'),400
    try:
        destino=_id(datos.get('id_objeto')); detalle=_texto(datos.get('detalle',''))
    except ValueError as e: return jsonify(error=str(e)),400
    uid=g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute(DESTINOS[tipo],(destino,)); objeto=cur.fetchone()
        if not objeto: return jsonify(error='Contenido no disponible'),404
        if objeto['autor']==uid: return jsonify(error='No puedes reportar tu propio contenido o cuenta'),400
        # Se permiten reportes aunque exista bloqueo: denunciar acoso no exige desbloquear.
        cur.execute('''INSERT INTO reportes(id_reportante,tipo,id_objeto,motivo,detalle) VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (id_reportante,tipo,id_objeto) WHERE estado='pendiente' DO NOTHING RETURNING id''',
                    (uid,tipo,destino,motivo,detalle))
        fila=cur.fetchone()
        if not fila: return jsonify(error='Ya tienes un reporte pendiente sobre este elemento'),409
        mysql.connection.commit()
    return jsonify(id=str(fila['id']),mensaje='Reporte enviado'),201


@moderacion_bp.route('/reportes', methods=['GET'])
@solo_admin
def listar_reportes():
    estado=request.args.get('estado','pendiente')
    if estado not in ('pendiente','atendido','descartado','todos'): return jsonify(error='Estado inválido'),400
    try: limite,antes=_pagina(request.args)
    except (ValueError,TypeError): return jsonify(error='Paginación inválida'),400
    with mysql.connection.cursor() as cur:
        cur.execute('''SELECT t.*,u.nombre_apellido AS reportante,
          COALESCE(p.titulo, r.contenido, c.contenido, v.nombre_apellido) AS contenido_reportado,
          COALESCE(p.id,r.id_pregunta,rc.id_pregunta) AS id_pregunta
          FROM reportes t JOIN usuarios u ON u.id=t.id_reportante
          LEFT JOIN preguntas p ON t.tipo='pregunta' AND p.id=t.id_objeto
          LEFT JOIN respuestas r ON t.tipo='respuesta' AND r.id=t.id_objeto
          LEFT JOIN comentarios c ON t.tipo='comentario' AND c.id=t.id_objeto
          LEFT JOIN respuestas rc ON rc.id=c.id_respuesta
          LEFT JOIN usuarios v ON t.tipo='usuario' AND v.id=t.id_objeto
          WHERE (%s='todos' OR t.estado=%s) AND t.id<%s ORDER BY t.id DESC LIMIT %s''',(estado,estado,antes,limite+1))
        filas=cur.fetchall()
    return jsonify(elementos=[dict(f,id=str(f['id'])) for f in filas[:limite]],siguiente=str(filas[limite-1]['id']) if len(filas)>limite else None),200


@moderacion_bp.route('/reportes/<int:identificador>', methods=['PUT'])
@solo_admin
def revisar_reporte(identificador):
    datos=request.get_json(); estado=datos.get('estado')
    if estado not in ('atendido','descartado'): return jsonify(error='Estado inválido'),400
    try: nota=_texto(datos.get('nota',''))
    except ValueError as e: return jsonify(error=str(e)),400
    with mysql.connection.cursor() as cur:
        cur.execute("UPDATE reportes SET estado=%s,nota_revision=%s,id_moderador=%s,fecha_revision=now() WHERE id=%s AND estado='pendiente' RETURNING id",(estado,nota,g.usuario['id'],identificador))
        if not cur.fetchone(): return jsonify(error='Reporte no disponible o ya revisado'),409
        registrar_accion(cur,estado+'_reporte','reporte',identificador,nota)
        mysql.connection.commit()
    return jsonify(estado=estado),200


@moderacion_bp.route('/usuarios/<int:identificador>/suspension', methods=['PUT'])
@solo_admin
def suspension(identificador):
    datos=request.get_json(); activo=datos.get('activo')
    if type(activo) is not bool: return jsonify(error='Activo debe ser booleano'),400
    try: nota=_texto(datos.get('motivo',''))
    except ValueError as e: return jsonify(error=str(e)),400
    if not nota: return jsonify(error='Indica el motivo'),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT rol,suspendido FROM usuarios WHERE id=%s FOR UPDATE',(identificador,)); fila=cur.fetchone()
        if not fila: return jsonify(error='Usuario no encontrado'),404
        if fila['rol']=='admin' or identificador==g.usuario['id']: return jsonify(error='No se pueden suspender administradores'),403
        if fila['suspendido']!=activo:
            cur.execute('UPDATE usuarios SET suspendido=%s,version_sesion=version_sesion+1 WHERE id=%s',(activo,identificador))
            registrar_accion(cur,'suspender' if activo else 'reactivar','usuario',identificador,nota)
        mysql.connection.commit()
    return jsonify(suspendido=activo),200


@moderacion_bp.route('/preguntas/<int:identificador>', methods=['PUT'])
@solo_admin
def moderar_pregunta(identificador):
    datos=request.get_json(); cambios={k:v for k,v in datos.items() if k in ('fijada','cerrada')}
    if not cambios or set(datos)-{'fijada','cerrada','motivo'} or any(type(v) is not bool for v in cambios.values()):
        return jsonify(error='Cambios inválidos'),400
    try: nota=_texto(datos.get('motivo',''))
    except ValueError as e: return jsonify(error=str(e)),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT fijada,cerrada FROM preguntas WHERE id=%s AND fecha_eliminacion IS NULL FOR UPDATE',(identificador,)); fila=cur.fetchone()
        if not fila: return jsonify(error='Pregunta no encontrada'),404
        for campo,valor in cambios.items():
            if fila[campo]!=valor:
                cur.execute(f'UPDATE preguntas SET {campo}=%s WHERE id=%s',(valor,identificador))
                registrar_accion(cur,('fijar' if valor else 'desfijar') if campo=='fijada' else ('cerrar' if valor else 'reabrir'),'pregunta',identificador,nota)
        mysql.connection.commit()
    return jsonify(dict(fila,**cambios)),200


@moderacion_bp.route('/estadisticas', methods=['GET'])
@solo_admin
def estadisticas():
    with mysql.connection.cursor() as cur:
        cur.execute('''SELECT
          (SELECT count(*) FROM usuarios) AS usuarios,
          (SELECT count(*) FROM usuarios WHERE suspendido) AS suspendidos,
          (SELECT count(*) FROM categorias) AS comunidades,
          (SELECT count(*) FROM preguntas WHERE fecha_eliminacion IS NULL) AS publicaciones,
          (SELECT count(*) FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta WHERE r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL) AS respuestas,
          (SELECT count(*) FROM comentarios c JOIN respuestas r ON r.id=c.id_respuesta JOIN preguntas p ON p.id=r.id_pregunta WHERE c.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL) AS comentarios,
          (SELECT count(*) FROM preguntas WHERE fecha_eliminacion IS NULL AND cerrada) AS cerradas,
          (SELECT count(*) FROM reportes WHERE estado='pendiente') AS reportes_pendientes''')
        return jsonify(dict(cur.fetchone())),200


@moderacion_bp.route('/historial', methods=['GET'])
@solo_admin
def historial():
    try: limite,antes=_pagina(request.args)
    except (ValueError,TypeError): return jsonify(error='Paginación inválida'),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT h.*,u.nombre_apellido AS administrador FROM historial_moderacion h JOIN usuarios u ON u.id=h.id_admin WHERE h.id<%s ORDER BY h.id DESC LIMIT %s',(antes,limite+1))
        filas=cur.fetchall()
    return jsonify(elementos=[dict(f,id=str(f['id'])) for f in filas[:limite]],siguiente=str(filas[limite-1]['id']) if len(filas)>limite else None),200
