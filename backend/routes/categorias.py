"""
Qué hace este archivo:
    CRUD de categorías del foro (temas donde se agrupan las preguntas).
    Listar es público; crear, editar y borrar exigen JWT y rol admin
    (se comprueba con _es_admin, no con el decorador solo_admin).
    No se borra una categoría si todavía tiene preguntas: esas filas
    guardan id_categoria y quedarían huérfanas o violarían la FK.

A qué servicio pertenece:
    Servicio de preguntas. Lo registra app_preguntas.py
    (app.register_blueprint(categorias_bp)), puerto 5001.

Qué importa:
    - flask: Blueprint, g (rol del token), jsonify, request.
    - extensions.mysql: conexión MySQL (tablas categorias y, al borrar,
      se consulta preguntas).
    - security.token_requerido: JWT válido → g.usuario.

Quién lo usa:
    Cliente del puerto 5001, rutas /categorias... GET /categorias no
    exige JWT; crear, editar y borrar sí.
    routes/preguntas.py necesita que existan categorías (id_categoria).
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido

# Prefijo /categorias → GET/POST /categorias y PUT/DELETE /categorias/<id>
categorias_bp = Blueprint("categorias", __name__, url_prefix="/categorias")


def _categoria_publica(fila):
    """
    Qué hace:
        Arma el JSON de una categoría (id, nombre, descripcion).

    Ruta y método:
        No es un endpoint. Lo usan las vistas de este archivo.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        fila: dict de una fila de categorias (DictCursor).

    Base de datos:
        No consulta.

    Respuestas:
        No envía HTTP. Devuelve un dict.
    """
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "descripcion": fila["descripcion"],
    }


def _buscar_categoria(cur, id_categoria):
    """
    Qué hace:
        Busca una categoría por id con el cursor que ya abrió la vista.

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        cur: cursor MySQL abierto.
        id_categoria: id numérico.

    Base de datos:
        Tabla categorias: SELECT WHERE id = %s. No escribe.

    Respuestas:
        No envía HTTP. Devuelve la fila o None.
    """
    cur.execute("SELECT id, nombre, descripcion FROM categorias WHERE id = %s", (id_categoria,))
    return cur.fetchone()


def _es_admin():
    """
    Qué hace:
        Mira el rol guardado en el JWT (g.usuario), no consulta usuarios.

    Ruta y método:
        No es un endpoint. Lo llaman crear/actualizar/eliminar.

    Quién puede usarlo:
        Uso interno. g.usuario lo rellena token_requerido (security.py).

    Entrada:
        Ninguna. Lee g.usuario["rol"].

    Base de datos:
        No consulta.

    Respuestas:
        True si rol == "admin"; si no, False. No envía HTTP.
    """
    return g.usuario.get("rol") == "admin"


@categorias_bp.route("", methods=["GET"])
def listar_categorias():
    """
    Qué hace:
        Lista todas las categorías.

    Ruta y método:
        GET /categorias

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        Ninguna en body ni URL.

    Base de datos:
        Tabla categorias: SELECT de todas las filas. No escribe.

    Respuestas:
        200: lista JSON.
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, descripcion FROM categorias")
    filas = cur.fetchall()
    cur.close()
    return jsonify([_categoria_publica(f) for f in filas]), 200


@categorias_bp.route("", methods=["POST"])
@token_requerido
def crear_categoria():
    """
    Qué hace:
        Crea una categoría nueva. Primero comprueba admin.

    Ruta y método:
        POST /categorias

    Quién puede usarlo:
        JWT + solo admin (_es_admin lee g.usuario["rol"]).

    Entrada:
        Body JSON: nombre (obligatorio), descripcion.

    Base de datos:
        Tabla categorias: INSERT + commit + SELECT del insertado.

    Respuestas:
        201: categoría creada.
        400: falta nombre (el mensaje también menciona descripcion).
        403: autenticado pero no admin.
        401: JWT inválido (token_requerido).
    """
    if not _es_admin():
        return jsonify({"error": "Se requiere rol de administrador"}), 403

    datos = request.get_json(silent=True) or {}
    nombre = (datos.get("nombre") or "").strip()
    descripcion = datos.get("descripcion") or ""

    if not nombre:
        return jsonify({"error": "nombre y descripcion son obligatorios"}), 400

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO categorias (nombre, descripcion) VALUES (%s, %s) RETURNING id",
        (nombre, descripcion),
    )
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    categoria = _buscar_categoria(cur, nuevo_id)
    cur.close()
    return jsonify(_categoria_publica(categoria)), 201


@categorias_bp.route("/<int:id_categoria>", methods=["PUT"])
@token_requerido
def actualizar_categoria(id_categoria):
    """
    Qué hace:
        Cambia nombre y/o descripcion. Si no mandan un campo, se deja
        el valor que ya tenía la fila.

    Ruta y método:
        PUT /categorias/<id_categoria>

    Quién puede usarlo:
        JWT + solo admin.

    Entrada:
        URL: id_categoria.
        Body JSON opcional: nombre, descripcion.

    Base de datos:
        Tabla categorias: SELECT por id, UPDATE, commit, SELECT otra vez.

    Respuestas:
        200: categoría actualizada.
        403: no es admin.
        404: id inexistente.
        401: JWT inválido.
    """
    if not _es_admin():
        return jsonify({"error": "Se requiere rol de administrador"}), 403

    cur = mysql.connection.cursor()
    categoria = _buscar_categoria(cur, id_categoria)
    if not categoria:
        cur.close()
        return jsonify({"error": "Categoría no encontrada"}), 404

    datos = request.get_json(silent=True) or {}
    nombre = (datos.get("nombre") or categoria["nombre"]).strip()
    descripcion = datos.get("descripcion") if datos.get("descripcion") is not None else categoria["descripcion"]

    cur.execute(
        "UPDATE categorias SET nombre = %s, descripcion = %s WHERE id = %s",
        (nombre, descripcion, id_categoria),
    )
    mysql.connection.commit()
    actualizada = _buscar_categoria(cur, id_categoria)
    cur.close()
    return jsonify(_categoria_publica(actualizada)), 200


@categorias_bp.route("/<int:id_categoria>", methods=["DELETE"])
@token_requerido
def eliminar_categoria(id_categoria):
    """
    Qué hace:
        Intenta borrar una categoría. Si hay preguntas con ese
        id_categoria, responde 409 y NO ejecuta el DELETE.
        Motivo: cada pregunta apunta a una categoría. Borrar el tema
        dejaría esas preguntas sin categoría válida (error de integridad
        en MySQL si hay FK, o datos rotos si no). El COUNT evita eso:
        primero hay que mover o borrar las preguntas.

    Ruta y método:
        DELETE /categorias/<id_categoria>

    Quién puede usarlo:
        JWT + solo admin.

    Entrada:
        URL: id_categoria.

    Base de datos:
        - categorias: SELECT por id
        - preguntas: SELECT COUNT(*) WHERE id_categoria = %s (solo lectura)
        - si el conteo es 0: DELETE en categorias + commit

    Respuestas:
        200: categoría eliminada.
        403: no es admin.
        404: id inexistente.
        409: todavía hay preguntas en esa categoría (no se borra).
        401: JWT inválido.
    """
    if not _es_admin():
        return jsonify({"error": "Se requiere rol de administrador"}), 403

    cur = mysql.connection.cursor()
    categoria = _buscar_categoria(cur, id_categoria)
    if not categoria:
        cur.close()
        return jsonify({"error": "Categoría no encontrada"}), 404

    # No se puede borrar si hay preguntas que apuntan a esta categoría
    cur.execute("SELECT COUNT(*) AS total FROM preguntas WHERE id_categoria = %s", (id_categoria,))
    if cur.fetchone()["total"] > 0:
        cur.close()
        return jsonify({
            "error": "No se puede eliminar la categoría porque tiene preguntas asociadas"
        }), 409

    cur.execute("DELETE FROM categorias WHERE id = %s", (id_categoria,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"mensaje": "Categoría eliminada"}), 200
