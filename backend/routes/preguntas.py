"""
Qué hace este archivo:
    CRUD de preguntas y un listado filtrado por categoría. Las lecturas
    GET son públicas (el foro se puede leer sin sesión). Crear, editar
    y borrar piden JWT. Crear usa el id del token como autor. Editar y
    borrar solo el autor o un admin (_es_autor_o_admin).

A qué servicio pertenece:
    Servicio de preguntas. Lo registra app_preguntas.py
    (app.register_blueprint(preguntas_bp)), puerto 5001.

Qué importa:
    - flask: Blueprint, g (id y rol del token), jsonify, request.
    - extensions.mysql: conexión MySQL.
    - security.token_requerido: JWT → g.usuario.

Quién lo usa:
    Cliente del puerto 5001, rutas /preguntas... Las GET no exigen JWT;
    el resto sí.
    Depende de que existan filas en usuarios (autor) y categorias
    (tema). El servicio de interacciones (respuestas, etc.) apunta
    a estas preguntas por id.

JOIN de SQL_PREGUNTA_DETALLE (por qué se unen tres tablas):
    La tabla preguntas solo guarda ids (id_usuario, id_categoria),
    no los nombres. El SELECT parte de preguntas (alias p) y hace
    JOIN (INNER JOIN) con:
    - usuarios u ON u.id = p.id_usuario  → trae nombre_apellido
      como nombre_autor (quién publicó).
    - categorias c ON c.id = p.id_categoria → trae c.nombre como
      nombre_categoria (en qué tema está).
    Así el JSON ya trae nombres y el cliente no tiene que pegarle
    a /usuarios ni a /categorias. INNER JOIN: si faltara el usuario
    o la categoría, esa pregunta no saldría en el listado.
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido

# Prefijo /preguntas → /preguntas, /preguntas/<id>, /preguntas/categoria/<id>
preguntas_bp = Blueprint("preguntas", __name__, url_prefix="/preguntas")

# Consulta base: pregunta + nombre del autor + nombre de la categoría
SQL_PREGUNTA_DETALLE = """
    SELECT p.id, p.id_usuario, p.id_categoria, p.titulo, p.contenido, p.fecha_creacion,
           u.nombre_apellido AS nombre_autor, c.nombre AS nombre_categoria
    FROM preguntas p
    JOIN usuarios u ON u.id = p.id_usuario
    JOIN categorias c ON c.id = p.id_categoria
"""


def _pregunta_publica(fila):
    """
    Qué hace:
        Pasa la fila del JOIN a un dict JSON (fechas como texto).

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno de las vistas.

    Entrada:
        fila: resultado de SQL_PREGUNTA_DETALLE.

    Base de datos:
        No consulta.

    Respuestas:
        No envía HTTP. Devuelve un dict.
    """
    return {
        "id": fila["id"],
        "id_usuario": fila["id_usuario"],
        "id_categoria": fila["id_categoria"],
        "titulo": fila["titulo"],
        "contenido": fila["contenido"],
        "fecha_creacion": str(fila["fecha_creacion"]),
        "nombre_autor": fila["nombre_autor"],
        "nombre_categoria": fila["nombre_categoria"],
    }


def _buscar_pregunta(cur, id_pregunta):
    """
    Qué hace:
        Una pregunta por id, con el mismo JOIN (autor + categoría).

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        cur: cursor ya abierto.
        id_pregunta: id de la URL o el id recién insertado.

    Base de datos:
        Tablas preguntas + usuarios + categorias (SQL_PREGUNTA_DETALLE).
        Solo SELECT.

    Respuestas:
        Fila o None. No envía HTTP.
    """
    cur.execute(SQL_PREGUNTA_DETALLE + " WHERE p.id = %s", (id_pregunta,))
    return cur.fetchone()


def _es_autor_o_admin(pregunta):
    """
    Qué hace:
        Decide si el usuario del token puede editar/borrar esta pregunta.
        Sí si g.usuario["id"] es el id_usuario de la fila (el autor),
        o si g.usuario["rol"] es "admin". Un compañero estudiante no.

    Ruta y método:
        No es un endpoint. Lo usan PUT y DELETE.

    Quién puede usarlo:
        Uso interno. g.usuario viene de token_requerido (security.py).

    Entrada:
        pregunta: fila con id_usuario (autor real en la BD).

    Base de datos:
        No consulta; compara token vs fila ya leída.

    Respuestas:
        True/False. No envía HTTP; las vistas traducen False a 403.
    """
    return g.usuario.get("id") == pregunta["id_usuario"] or g.usuario.get("rol") == "admin"


@preguntas_bp.route("", methods=["GET"])
def listar_preguntas():
    """
    Qué hace:
        Lista todas las preguntas, la más reciente primero.

    Ruta y método:
        GET /preguntas

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        Ninguna en body ni URL.

    Base de datos:
        SELECT con JOIN preguntas + usuarios + categorias.
        No escribe.

    Respuestas:
        200: lista JSON (puede ser []).
    """
    cur = mysql.connection.cursor()
    cur.execute(SQL_PREGUNTA_DETALLE + " ORDER BY p.fecha_creacion DESC")
    filas = cur.fetchall()
    cur.close()
    return jsonify([_pregunta_publica(f) for f in filas]), 200


@preguntas_bp.route("/categoria/<int:id_categoria>", methods=["GET"])
def listar_por_categoria(id_categoria):
    """
    Qué hace:
        Igual que el listado, filtrado por p.id_categoria.

    Ruta y método:
        GET /preguntas/categoria/<id_categoria>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_categoria.

    Base de datos:
        Mismo JOIN; WHERE p.id_categoria = %s. No comprueba si la
        categoría existe (si no hay filas, lista vacía).

    Respuestas:
        200: lista (vacía si no hay preguntas o el id no existe).
    """
    cur = mysql.connection.cursor()
    cur.execute(
        SQL_PREGUNTA_DETALLE + " WHERE p.id_categoria = %s ORDER BY p.fecha_creacion DESC",
        (id_categoria,),
    )
    filas = cur.fetchall()
    cur.close()
    return jsonify([_pregunta_publica(f) for f in filas]), 200


@preguntas_bp.route("/<int:id_pregunta>", methods=["GET"])
def obtener_pregunta(id_pregunta):
    """
    Qué hace:
        Una pregunta por id, con nombres de autor y categoría.

    Ruta y método:
        GET /preguntas/<id_pregunta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_pregunta.

    Base de datos:
        SELECT del JOIN filtrado por p.id. No escribe.

    Respuestas:
        200: pregunta.
        404: no hay fila (o el JOIN no encontró usuario/categoría).
    """
    cur = mysql.connection.cursor()
    pregunta = _buscar_pregunta(cur, id_pregunta)
    cur.close()
    if not pregunta:
        return jsonify({"error": "Pregunta no encontrada"}), 404
    return jsonify(_pregunta_publica(pregunta)), 200


@preguntas_bp.route("", methods=["POST"])
@token_requerido
def crear_pregunta():
    """
    Qué hace:
        Publica una pregunta. id_categoria, titulo y contenido van en
        el body. El autor NO se toma del body: sale de g.usuario["id"]
        (el JWT). Así nadie puede publicar haciéndose pasar por otro.

    Ruta y método:
        POST /preguntas

    Quién puede usarlo:
        JWT. Cualquier autenticado (estudiante o admin).

    Entrada:
        Body JSON: id_categoria, titulo, contenido.
        Autor: g.usuario["id"] (token_requerido → security.py).

    Base de datos:
        - categorias: SELECT id (si no existe → 404, no inserta)
        - preguntas: INSERT (id_usuario, id_categoria, titulo, contenido)
        - commit
        - SELECT del JOIN sobre el id insertado (RETURNING id)

    Respuestas:
        201: pregunta creada (con nombre_autor y nombre_categoria).
        400: falta id_categoria, titulo o contenido.
        404: esa categoría no existe.
        401: JWT inválido.
    """
    datos = request.get_json(silent=True) or {}
    id_categoria = datos.get("id_categoria")
    titulo = (datos.get("titulo") or "").strip()
    contenido = (datos.get("contenido") or "").strip()

    if id_categoria is None or not titulo or not contenido:
        return jsonify({"error": "id_categoria, titulo y contenido son obligatorios"}), 400

    # El autor sale del token, no del body
    id_usuario = g.usuario.get("id")

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM categorias WHERE id = %s", (id_categoria,))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "Categoría no encontrada"}), 404

    cur.execute(
        "INSERT INTO preguntas (id_usuario, id_categoria, titulo, contenido) VALUES (%s, %s, %s, %s) RETURNING id",
        (id_usuario, id_categoria, titulo, contenido),
    )
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    pregunta = _buscar_pregunta(cur, nuevo_id)
    cur.close()
    return jsonify(_pregunta_publica(pregunta)), 201


@preguntas_bp.route("/<int:id_pregunta>", methods=["PUT"])
@token_requerido
def actualizar_pregunta(id_pregunta):
    """
    Qué hace:
        Cambia titulo y/o contenido. No cambia de categoría ni de autor.
        Permiso: _es_autor_o_admin (dueño de la fila o admin).

    Ruta y método:
        PUT /preguntas/<id_pregunta>

    Quién puede usarlo:
        JWT, y además autor o admin.

    Entrada:
        URL: id_pregunta.
        Body JSON opcional: titulo, contenido.

    Base de datos:
        Tabla preguntas (+ JOIN al leer): SELECT, UPDATE, commit, SELECT.

    Respuestas:
        200: pregunta actualizada.
        403: autenticado pero ni autor ni admin.
        404: id inexistente.
        401: JWT inválido.
    """
    cur = mysql.connection.cursor()
    pregunta = _buscar_pregunta(cur, id_pregunta)
    if not pregunta:
        cur.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404

    if not _es_autor_o_admin(pregunta):
        cur.close()
        return jsonify({"error": "No autorizado para modificar esta pregunta"}), 403

    datos = request.get_json(silent=True) or {}
    titulo = (datos.get("titulo") or pregunta["titulo"]).strip()
    contenido = (datos.get("contenido") or pregunta["contenido"]).strip()

    cur.execute(
        "UPDATE preguntas SET titulo = %s, contenido = %s WHERE id = %s",
        (titulo, contenido, id_pregunta),
    )
    mysql.connection.commit()
    actualizada = _buscar_pregunta(cur, id_pregunta)
    cur.close()
    return jsonify(_pregunta_publica(actualizada)), 200


@preguntas_bp.route("/<int:id_pregunta>", methods=["DELETE"])
@token_requerido
def eliminar_pregunta(id_pregunta):
    """
    Qué hace:
        Borra la pregunta. Misma regla que el PUT: autor o admin.

    Ruta y método:
        DELETE /preguntas/<id_pregunta>

    Quién puede usarlo:
        JWT, y además autor o admin.

    Entrada:
        URL: id_pregunta.

    Base de datos:
        preguntas: SELECT (con JOIN), DELETE WHERE id = %s, commit.
        No mira respuestas/comentarios/votos en este archivo.

    Respuestas:
        200: {"mensaje": "Pregunta eliminada"}.
        403: ni autor ni admin.
        404: id inexistente.
        401: JWT inválido.
    """
    cur = mysql.connection.cursor()
    pregunta = _buscar_pregunta(cur, id_pregunta)
    if not pregunta:
        cur.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404

    if not _es_autor_o_admin(pregunta):
        cur.close()
        return jsonify({"error": "No autorizado para eliminar esta pregunta"}), 403

    cur.execute("DELETE FROM preguntas WHERE id = %s", (id_pregunta,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"mensaje": "Pregunta eliminada"}), 200
