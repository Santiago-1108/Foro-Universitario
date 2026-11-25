"""
Qué hace este archivo:
    Comentarios sobre una respuesta (no sobre la pregunta). Crear
    comprueba que la respuesta exista (SELECT en respuestas) antes
    del INSERT. Listar por respuesta no hace esa comprobación.
    No hay PUT: solo listar, crear y borrar (autor o admin).

A qué servicio pertenece:
    Servicio de interacciones. Lo registra app_interacciones.py
    (app.register_blueprint(comentarios_bp)), puerto 5002.

Qué importa:
    - flask: Blueprint, g, jsonify, request.
    - extensions.mysql: conexión (comentarios, respuestas, usuarios).
    - security.token_requerido: JWT → g.usuario.

Quién lo usa:
    Cliente del puerto 5002, rutas /comentarios... Listar por respuesta
    es público; crear y borrar piden JWT.
    Depende de respuestas.py (id_respuesta debe existir al crear).
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido, _usuario_desde_token

# Prefijo /comentarios → POST /comentarios, GET .../respuesta/<id>, DELETE .../<id>
comentarios_bp = Blueprint("comentarios", __name__, url_prefix="/comentarios")

# Comentario + nombre del autor
SQL_COMENTARIO_DETALLE = """
    SELECT c.id, c.id_usuario, c.id_respuesta, c.contenido, c.fecha_creacion, c.id_comentario_padre, c.fecha_eliminacion,
           u.nombre_apellido AS nombre_autor, u.avatar_url AS avatar_autor
    FROM comentarios c
    JOIN usuarios u ON u.id = c.id_usuario
    JOIN respuestas r ON r.id=c.id_respuesta
    JOIN preguntas p ON p.id=r.id_pregunta
"""


def _comentario_publico(fila):
    """
    Qué hace:
        Pasa la fila del JOIN a un dict JSON.

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        fila: resultado de SQL_COMENTARIO_DETALLE.

    Base de datos:
        No consulta.

    Respuestas:
        Dict. No envía HTTP.
    """
    return {
        "id": fila["id"],
        "id_usuario": None if fila.get("fecha_eliminacion") else fila["id_usuario"],
        "id_comentario_padre": fila.get("id_comentario_padre"),
        "eliminado": bool(fila.get("fecha_eliminacion")),
        "id_respuesta": fila["id_respuesta"],
        "contenido": "[Comentario eliminado]" if fila.get("fecha_eliminacion") else fila["contenido"],
        "fecha_creacion": str(fila["fecha_creacion"]),
        "nombre_autor": "" if fila.get("fecha_eliminacion") else fila["nombre_autor"],
        "avatar_autor": None if fila.get("fecha_eliminacion") else fila.get("avatar_autor"),
    }


def _buscar_comentario(cur, id_comentario):
    """
    Qué hace:
        Un comentario por id, con nombre del autor.

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        cur: cursor abierto.
        id_comentario: id numérico.

    Base de datos:
        SELECT comentarios + usuarios. No escribe.

    Respuestas:
        Fila o None. No envía HTTP.
    """
    cur.execute(SQL_COMENTARIO_DETALLE + " WHERE c.id = %s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL", (id_comentario,))
    return cur.fetchone()


def _es_autor_o_admin(registro):
    """
    Qué hace:
        True si el token es del autor de la fila o el rol es admin.

    Ruta y método:
        No es un endpoint. Lo usa DELETE.

    Quién puede usarlo:
        Uso interno. g.usuario: token_requerido (security.py).

    Entrada:
        registro: fila con id_usuario.

    Base de datos:
        No consulta.

    Respuestas:
        True/False. DELETE convierte False en 403.
    """
    return g.usuario.get("id") == registro["id_usuario"] or g.usuario.get("rol") == "admin"


@comentarios_bp.route("/respuesta/<int:id_respuesta>", methods=["GET"])
def listar_por_respuesta(id_respuesta):
    """
    Qué hace:
        Lista comentarios de una respuesta, del más viejo al más nuevo.
        No hace SELECT previo en respuestas: si el id no existe,
        fetchall queda vacío y se responde 200 [].

    Ruta y método:
        GET /comentarios/respuesta/<id_respuesta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_respuesta.

    Base de datos:
        comentarios + usuarios: SELECT WHERE c.id_respuesta = %s.
        No escribe. No consulta la tabla respuestas.

    Respuestas:
        200: lista (vacía si no hay comentarios o la respuesta no existe).
    """
    uid = None
    gestion = request.args.get('gestion') == '1'
    if request.headers.get('Authorization') or gestion:
        identidad,error=_usuario_desde_token()
        if error: return error
        if gestion and identidad['rol'] != 'admin': return jsonify(error='No autorizado'),403
        uid=None if gestion else identidad['id']
    cur = mysql.connection.cursor()
    cur.execute(
        SQL_COMENTARIO_DETALLE + " WHERE c.id_respuesta = %s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario) AND NOT public.foro_hay_bloqueo(%s,c.id_usuario) ORDER BY c.fecha_creacion ASC, c.id ASC",
        (id_respuesta,uid,uid,uid),
    )
    filas = cur.fetchall()
    cur.close()
    return jsonify([_comentario_publico(f) for f in filas]), 200


@comentarios_bp.route("", methods=["POST"])
@token_requerido
def crear_comentario():
    """
    Qué hace:
        Crea un comentario. Antes del INSERT: SELECT en respuestas
        con el id_respuesta del body. Si no hay fila → 404 y no inserta
        (el comentario tiene que colgar de una respuesta real).
        El autor es g.usuario["id"], no el body.

    Ruta y método:
        POST /comentarios

    Quién puede usarlo:
        JWT. Cualquier autenticado.

    Entrada:
        Body JSON: id_respuesta, contenido.
        Autor: g.usuario["id"] (security.py).

    Base de datos:
        - respuestas: SELECT id (¿existe?)
        - comentarios: INSERT (id_usuario, id_respuesta, contenido)
        - commit
        - SELECT del JOIN sobre el id insertado (RETURNING id)

    Respuestas:
        201: comentario creado.
        400: falta id_respuesta o contenido.
        404: esa respuesta no existe (no se inserta).
        401: JWT inválido.
    """
    datos = request.get_json(silent=True) or {}
    id_respuesta = datos.get("id_respuesta")
    contenido = (datos.get("contenido") or "").strip()

    if id_respuesta is None or not contenido:
        return jsonify({"error": "id_respuesta y contenido son obligatorios"}), 400

    # El autor sale del token, no del body
    id_usuario = g.usuario.get("id")

    cur = mysql.connection.cursor()
    cur.execute("SELECT p.id,p.cerrada FROM preguntas p JOIN respuestas r ON r.id_pregunta=p.id WHERE r.id=%s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario) FOR UPDATE OF p", (id_respuesta,id_usuario,id_usuario))
    pregunta = cur.fetchone()
    if not pregunta:
        cur.close()
        return jsonify({"error": "Respuesta no encontrada"}), 404

    if pregunta.get("cerrada"):
        cur.close()
        return jsonify(error="Conversación cerrada por moderación"), 409

    cur.execute("SELECT id FROM respuestas WHERE id=%s AND fecha_eliminacion IS NULL", (id_respuesta,))
    if not cur.fetchone():
        cur.close()
        return jsonify(error="Respuesta no encontrada"),404
    padre = datos.get("id_comentario_padre")
    if padre is not None:
        if type(padre) is not int or not 0 < padre <= 9223372036854775807:
            cur.close()
            return jsonify(error="Comentario padre inválido"), 400
        cur.execute("SELECT id FROM comentarios WHERE id=%s AND id_respuesta=%s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario)", (padre,id_respuesta,id_usuario))
        if not cur.fetchone():
            cur.close()
            return jsonify(error="Comentario padre no disponible en esta respuesta"), 404
    cur.execute("INSERT INTO comentarios (id_usuario,id_respuesta,contenido,id_comentario_padre) VALUES (%s,%s,%s,%s) RETURNING id", (id_usuario,id_respuesta,contenido,padre))
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    comentario = _buscar_comentario(cur, nuevo_id)
    cur.close()
    return jsonify(_comentario_publico(comentario)), 201


@comentarios_bp.route("/<int:id_comentario>", methods=["DELETE"])
@token_requerido
def eliminar_comentario(id_comentario):
    """
    Qué hace:
        Borra un comentario. Solo autor o admin. No hay endpoint PUT.

    Ruta y método:
        DELETE /comentarios/<id_comentario>

    Quién puede usarlo:
        JWT, y además autor o admin.

    Entrada:
        URL: id_comentario.

    Base de datos:
        comentarios: SELECT (JOIN), UPDATE fecha_eliminacion, commit.

    Respuestas:
        200: {"mensaje": "Comentario eliminado"}.
        403: ni autor ni admin.
        404: id inexistente.
        401: JWT inválido.
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.id FROM preguntas p JOIN respuestas r ON r.id_pregunta=p.id JOIN comentarios c ON c.id_respuesta=r.id WHERE c.id=%s AND p.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL FOR UPDATE OF p", (id_comentario,))
    comentario = _buscar_comentario(cur,id_comentario) if cur.fetchone() else None
    if not comentario or comentario.get("fecha_eliminacion"):
        cur.close()
        return jsonify({"error": "Comentario no encontrado"}), 404

    if not _es_autor_o_admin(comentario):
        cur.close()
        return jsonify({"error": "No autorizado para eliminar este comentario"}), 403

    cur.execute("UPDATE comentarios SET fecha_eliminacion=now() WHERE id = %s", (id_comentario,))
    if g.usuario["rol"] == "admin":
        cur.execute("INSERT INTO historial_moderacion(id_admin,accion,tipo,id_objeto) VALUES (%s,'eliminar','comentario',%s)", (g.usuario["id"],id_comentario))
    mysql.connection.commit()
    cur.close()
    return jsonify({"mensaje": "Comentario eliminado"}), 200
