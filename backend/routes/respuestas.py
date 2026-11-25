"""
Qué hace este archivo:
    CRUD de respuestas a una pregunta del foro. Antes de listar por
    pregunta o de insertar, comprueba que esa pregunta exista
    (SELECT en preguntas). El autor al crear sale del JWT. Editar y
    borrar: autor o admin.

A qué servicio pertenece:
    Servicio de interacciones. Lo registra app_interacciones.py
    (app.register_blueprint(respuestas_bp)), puerto 5002.

Qué importa:
    - flask: Blueprint, g, jsonify, request.
    - extensions.mysql: conexión MySQL (respuestas, preguntas, usuarios).
    - security.token_requerido: JWT → g.usuario.

Quién lo usa:
    Cliente del puerto 5002, rutas /respuestas... Las GET son públicas;
    crear, editar y borrar piden JWT.
    Las preguntas viven en el servicio de preguntas (misma BD).
    comentarios.py y votos.py pueden apuntar a una respuesta por id.
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido, _usuario_desde_token

# Prefijo /respuestas → /respuestas, /respuestas/<id>, /respuestas/pregunta/<id>
respuestas_bp = Blueprint("respuestas", __name__, url_prefix="/respuestas")

# Respuesta + nombre del autor
SQL_RESPUESTA_DETALLE = """
    SELECT r.id, r.id_usuario, r.id_pregunta, r.contenido, r.fecha_creacion,
           u.nombre_apellido AS nombre_autor, u.avatar_url AS avatar_autor
    FROM respuestas r
    JOIN usuarios u ON u.id = r.id_usuario
    JOIN preguntas p ON p.id = r.id_pregunta
"""


def _respuesta_publica(fila):
    """
    Qué hace:
        Pasa la fila del JOIN a un dict JSON (sin datos extra).

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        fila: resultado de SQL_RESPUESTA_DETALLE.

    Base de datos:
        No consulta.

    Respuestas:
        Dict. No envía HTTP.
    """
    return {
        "id": fila["id"],
        "id_usuario": fila["id_usuario"],
        "id_pregunta": fila["id_pregunta"],
        "contenido": fila["contenido"],
        "fecha_creacion": str(fila["fecha_creacion"]),
        "nombre_autor": fila["nombre_autor"],
        "avatar_autor": fila.get("avatar_autor"),
    }


def _buscar_respuesta(cur, id_respuesta):
    """
    Qué hace:
        Una respuesta por id, con el nombre del autor (JOIN usuarios).

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        cur: cursor abierto.
        id_respuesta: id numérico.

    Base de datos:
        SELECT en respuestas + usuarios. No escribe.

    Respuestas:
        Fila o None. No envía HTTP.
    """
    cur.execute(SQL_RESPUESTA_DETALLE + " WHERE r.id = %s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL", (id_respuesta,))
    return cur.fetchone()


def _es_autor_o_admin(registro):
    """
    Qué hace:
        True si el id del token es el autor de la fila, o el rol es admin.

    Ruta y método:
        No es un endpoint. Lo usan PUT y DELETE.

    Quién puede usarlo:
        Uso interno. g.usuario lo pone token_requerido (security.py).

    Entrada:
        registro: fila con id_usuario.

    Base de datos:
        No consulta.

    Respuestas:
        True/False. Las vistas convierten False en 403.
    """
    return g.usuario.get("id") == registro["id_usuario"] or g.usuario.get("rol") == "admin"


@respuestas_bp.route("/pregunta/<int:id_pregunta>", methods=["GET"])
def listar_por_pregunta(id_pregunta):
    """
    Qué hace:
        Lista las respuestas de una pregunta, de la más vieja a la más
        nueva. Primero SELECT en preguntas: si no hay fila → 404
        (no se confunde "pregunta inexistente" con "aún no hay respuestas").

    Ruta y método:
        GET /respuestas/pregunta/<id_pregunta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_pregunta.

    Base de datos:
        - preguntas: SELECT id (¿existe?)
        - respuestas + usuarios: SELECT filtrado por r.id_pregunta
        No escribe.

    Respuestas:
        200: lista (puede ser [] si la pregunta existe pero no tiene respuestas).
        404: esa pregunta no está en la tabla preguntas.
    """
    uid = None
    gestion = request.args.get('gestion') == '1'
    if request.headers.get('Authorization') or gestion:
        identidad,error=_usuario_desde_token()
        if error: return error
        if gestion and identidad['rol'] != 'admin': return jsonify(error='No autorizado'),403
        uid=None if gestion else identidad['id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM preguntas WHERE id = %s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario)", (id_pregunta,uid))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404

    cur.execute(
        SQL_RESPUESTA_DETALLE + " WHERE r.id_pregunta = %s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,r.id_usuario) ORDER BY r.fecha_creacion ASC, r.id ASC",
        (id_pregunta,uid),
    )
    filas = cur.fetchall()
    cur.close()
    return jsonify([_respuesta_publica(f) for f in filas]), 200


@respuestas_bp.route("/<int:id_respuesta>", methods=["GET"])
def obtener_respuesta(id_respuesta):
    """
    Qué hace:
        Devuelve una respuesta por su id.

    Ruta y método:
        GET /respuestas/<id_respuesta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_respuesta.

    Base de datos:
        SELECT del JOIN respuestas + usuarios. No escribe.

    Respuestas:
        200: respuesta.
        404: no hay esa fila.
    """
    cur = mysql.connection.cursor()
    respuesta = _buscar_respuesta(cur, id_respuesta)
    if respuesta and request.headers.get('Authorization'):
        identidad,error=_usuario_desde_token()
        if error: cur.close(); return error
        cur.execute('SELECT NOT public.foro_hay_bloqueo(%s,r.id_usuario) AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AS visible FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta WHERE r.id=%s',(identidad['id'],identidad['id'],id_respuesta))
        if not cur.fetchone()['visible']: respuesta=None
    cur.close()
    if not respuesta:
        return jsonify({"error": "Respuesta no encontrada"}), 404
    return jsonify(_respuesta_publica(respuesta)), 200


@respuestas_bp.route("", methods=["POST"])
@token_requerido
def crear_respuesta():
    """
    Qué hace:
        Publica una respuesta. Antes del INSERT: SELECT en preguntas
        con el id_pregunta del body. Si no existe, 404 y no inserta
        (evita una respuesta huérfana o un error de FK).
        El autor es g.usuario["id"], no un campo del JSON.

    Ruta y método:
        POST /respuestas

    Quién puede usarlo:
        JWT. Cualquier autenticado.

    Entrada:
        Body JSON: id_pregunta, contenido.
        Autor: g.usuario["id"] (security.py).

    Base de datos:
        - preguntas: SELECT id
        - respuestas: INSERT (id_usuario, id_pregunta, contenido)
        - commit
        - SELECT del JOIN sobre el id insertado (RETURNING id)

    Respuestas:
        201: respuesta creada.
        400: falta id_pregunta o contenido.
        404: la pregunta no existe (no se inserta).
        401: JWT inválido.
    """
    datos = request.get_json(silent=True) or {}
    id_pregunta = datos.get("id_pregunta")
    contenido = (datos.get("contenido") or "").strip()

    if id_pregunta is None or not contenido:
        return jsonify({"error": "id_pregunta y contenido son obligatorios"}), 400

    # El autor sale del token, no del body
    id_usuario = g.usuario.get("id")

    cur = mysql.connection.cursor()
    cur.execute("SELECT id,cerrada FROM preguntas WHERE id = %s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario) FOR UPDATE", (id_pregunta,id_usuario))
    pregunta = cur.fetchone()
    if not pregunta:
        cur.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404

    if pregunta.get("cerrada"):
        cur.close()
        return jsonify(error="Conversación cerrada por moderación"), 409

    cur.execute(
        "INSERT INTO respuestas (id_usuario, id_pregunta, contenido) VALUES (%s, %s, %s) RETURNING id",
        (id_usuario, id_pregunta, contenido),
    )
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    respuesta = _buscar_respuesta(cur, nuevo_id)
    cur.close()
    return jsonify(_respuesta_publica(respuesta)), 201


@respuestas_bp.route("/<int:id_respuesta>", methods=["PUT"])
@token_requerido
def actualizar_respuesta(id_respuesta):
    """
    Qué hace:
        Cambia el contenido. Solo autor o admin.

    Ruta y método:
        PUT /respuestas/<id_respuesta>

    Quién puede usarlo:
        JWT, y además autor o admin.

    Entrada:
        URL: id_respuesta.
        Body JSON opcional: contenido.

    Base de datos:
        respuestas: SELECT, UPDATE contenido, commit, SELECT.

    Respuestas:
        200: respuesta actualizada.
        403: ni autor ni admin.
        404: id inexistente.
        401: JWT inválido.
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.id FROM preguntas p JOIN respuestas r ON r.id_pregunta=p.id WHERE r.id=%s AND p.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL FOR UPDATE OF p", (id_respuesta,))
    bloqueo = cur.fetchone()
    respuesta = _buscar_respuesta(cur, id_respuesta) if bloqueo else None
    if not respuesta:
        cur.close()
        return jsonify({"error": "Respuesta no encontrada"}), 404

    if not _es_autor_o_admin(respuesta):
        cur.close()
        return jsonify({"error": "No autorizado para modificar esta respuesta"}), 403

    datos = request.get_json(silent=True) or {}
    contenido = (datos.get("contenido") or respuesta["contenido"]).strip()

    cur.execute(
        "UPDATE respuestas SET contenido = %s WHERE id = %s",
        (contenido, id_respuesta),
    )
    mysql.connection.commit()
    actualizada = _buscar_respuesta(cur, id_respuesta)
    cur.close()
    return jsonify(_respuesta_publica(actualizada)), 200


@respuestas_bp.route("/<int:id_respuesta>", methods=["DELETE"])
@token_requerido
def eliminar_respuesta(id_respuesta):
    """
    Qué hace:
        Borra la respuesta. Solo autor o admin.

    Ruta y método:
        DELETE /respuestas/<id_respuesta>

    Quién puede usarlo:
        JWT, y además autor o admin.

    Entrada:
        URL: id_respuesta.

    Base de datos:
        respuestas: SELECT, UPDATE fecha_eliminacion, commit.
        Conserva comentarios y votos; desmarca la solución si corresponde.

    Respuestas:
        200: {"mensaje": "Respuesta eliminada"}.
        403: ni autor ni admin.
        404: id inexistente.
        401: JWT inválido.
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.id FROM preguntas p JOIN respuestas r ON r.id_pregunta=p.id WHERE r.id=%s AND p.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL FOR UPDATE OF p", (id_respuesta,))
    bloqueo = cur.fetchone()
    respuesta = _buscar_respuesta(cur, id_respuesta) if bloqueo else None
    if not respuesta:
        cur.close()
        return jsonify({"error": "Respuesta no encontrada"}), 404

    if not _es_autor_o_admin(respuesta):
        cur.close()
        return jsonify({"error": "No autorizado para eliminar esta respuesta"}), 403

    cur.execute("UPDATE preguntas SET id_respuesta_aceptada=NULL WHERE id=%s AND id_respuesta_aceptada=%s", (respuesta["id_pregunta"],id_respuesta))
    cur.execute("UPDATE respuestas SET fecha_eliminacion=now() WHERE id=%s", (id_respuesta,))
    if g.usuario["rol"] == "admin":
        cur.execute("INSERT INTO historial_moderacion(id_admin,accion,tipo,id_objeto) VALUES (%s,'eliminar','respuesta',%s)", (g.usuario["id"],id_respuesta))
    mysql.connection.commit()
    cur.close()
    return jsonify({"mensaje": "Respuesta eliminada"}), 200
