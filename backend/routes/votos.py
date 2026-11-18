"""
Qué hace este archivo:
    Votos +1 o -1 sobre una pregunta O una respuesta (nunca las dos
    a la vez, ni ninguna). El votante sale del JWT. Un usuario no
    puede votar dos veces lo mismo (409). Los GET suman los +1/-1
    (total_votos) y cuentan filas (cantidad). Borrar: solo el dueño
    del voto, no el admin.

A qué servicio pertenece:
    Servicio de interacciones. Lo registra app_interacciones.py
    (app.register_blueprint(votos_bp)), puerto 5002.

Qué importa:
    - flask: Blueprint, g, jsonify, request.
    - extensions.mysql: conexión (votos, preguntas, respuestas).
    - security.token_requerido: JWT → g.usuario.

Quién lo usa:
    Cliente del puerto 5002, rutas /votos... Los GET de totales son
    públicos; crear y borrar un voto piden JWT.
    Depende de que existan la pregunta (servicio de preguntas) o
    la respuesta (respuestas.py) al crear el voto.

Cómo se vota una sola cosa:
    El body trae voto y, como destino, id_pregunta y/o id_respuesta.
    hay_pregunta y hay_respuesta son True/False. Si son iguales
    (los dos True o los dos False) → 400: hay que mandar exactamente
    uno. Luego, si hay pregunta, id_respuesta se guarda NULL (y al
    revés). Así cada fila apunta a un único objetivo.

Cómo se evita el voto duplicado:
    Tras comprobar que el objetivo existe, SELECT en votos con
    id_usuario del token + id_pregunta (o id_respuesta). Si ya hay
    fila → 409 y no hay INSERT. No hay PUT: para cambiar de +1 a -1
    habría que DELETE y volver a POST.

Cómo se calculan total y cantidad:
    GET suma voto (1 o -1) con SUM: es el puntaje neto
    (3 likes y 1 dislike → total 2). COUNT(*) es cuántas personas
    votaron, sin importar el signo. COALESCE(..., 0) hace que, si
    no hay filas, SUM sea 0 y no NULL. Esos GET no verifican que
    la pregunta/respuesta exista: sin votos responden 0 y 0.
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido

# Prefijo /votos → POST /votos, GET .../pregunta|respuesta/<id>, DELETE .../<id>
votos_bp = Blueprint("votos", __name__, url_prefix="/votos")


def _voto_publico(fila):
    """
    Qué hace:
        JSON de un voto. Uno de id_pregunta / id_respuesta irá None.

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        fila: registro de la tabla votos.

    Base de datos:
        No consulta.

    Respuestas:
        Dict. No envía HTTP.
    """
    return {
        "id": fila["id"],
        "id_usuario": fila["id_usuario"],
        "id_pregunta": fila["id_pregunta"],
        "id_respuesta": fila["id_respuesta"],
        "voto": fila["voto"],
    }


def _buscar_voto(cur, id_voto):
    """
    Qué hace:
        Un voto por id.

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        cur: cursor abierto.
        id_voto: id numérico.

    Base de datos:
        Tabla votos: SELECT. No escribe.

    Respuestas:
        Fila o None. No envía HTTP.
    """
    cur.execute(
        "SELECT id, id_usuario, id_pregunta, id_respuesta, voto FROM votos WHERE id = %s",
        (id_voto,),
    )
    return cur.fetchone()


@votos_bp.route("", methods=["POST"])
@token_requerido
def crear_voto():
    """
    Qué hace:
        Registra un +1 o -1. Pasos:
        1) XOR: exactamente uno de id_pregunta / id_respuesta.
        2) voto debe ser 1 o -1 (no 0 ni otro número).
        3) id_usuario = g.usuario["id"] (no viene en el body).
        4) SELECT en preguntas o respuestas: si no existe → 404.
        5) SELECT si este usuario ya votó ese id → 409.
        6) INSERT con el otro id en NULL + commit.

    Ruta y método:
        POST /votos

    Quién puede usarlo:
        JWT. Cualquier autenticado.

    Entrada:
        Body JSON: voto (1 o -1) y exactamente uno de
        id_pregunta o id_respuesta.

    Base de datos:
        - preguntas o respuestas: SELECT id
        - votos: SELECT duplicado; INSERT; commit; SELECT del nuevo

    Respuestas:
        201: voto creado.
        400: los dos ids, ninguno, o voto distinto de 1/-1.
        404: pregunta o respuesta inexistente (no inserta).
        409: este usuario ya votó esa pregunta o respuesta.
        401: JWT inválido.
    """
    datos = request.get_json(silent=True) or {}
    voto = datos.get("voto")
    id_pregunta = datos.get("id_pregunta")
    id_respuesta = datos.get("id_respuesta")

    # Debe venir exactamente uno: pregunta o respuesta
    hay_pregunta = id_pregunta is not None
    hay_respuesta = id_respuesta is not None
    if hay_pregunta == hay_respuesta:
        return jsonify({
            "error": "Debe enviar exactamente uno entre id_pregunta e id_respuesta"
        }), 400

    if voto not in (1, -1):
        return jsonify({"error": "voto inválido; debe ser 1 o -1"}), 400

    # El votante sale del token, no del body
    id_usuario = g.usuario.get("id")

    cur = mysql.connection.cursor()
    if hay_pregunta:
        cur.execute("SELECT id FROM preguntas WHERE id = %s", (id_pregunta,))
        if not cur.fetchone():
            cur.close()
            return jsonify({"error": "Pregunta no encontrada"}), 404

        cur.execute(
            "SELECT id FROM votos WHERE id_usuario = %s AND id_pregunta = %s",
            (id_usuario, id_pregunta),
        )
        if cur.fetchone():
            cur.close()
            return jsonify({"error": "Ya votó esta pregunta"}), 409

        cur.execute(
            "INSERT INTO votos (id_usuario, id_pregunta, id_respuesta, voto) VALUES (%s, %s, NULL, %s) RETURNING id",
            (id_usuario, id_pregunta, voto),
        )
    else:
        cur.execute("SELECT id FROM respuestas WHERE id = %s", (id_respuesta,))
        if not cur.fetchone():
            cur.close()
            return jsonify({"error": "Respuesta no encontrada"}), 404

        cur.execute(
            "SELECT id FROM votos WHERE id_usuario = %s AND id_respuesta = %s",
            (id_usuario, id_respuesta),
        )
        if cur.fetchone():
            cur.close()
            return jsonify({"error": "Ya votó esta respuesta"}), 409

        cur.execute(
            "INSERT INTO votos (id_usuario, id_pregunta, id_respuesta, voto) VALUES (%s, NULL, %s, %s) RETURNING id",
            (id_usuario, id_respuesta, voto),
        )

    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    creado = _buscar_voto(cur, nuevo_id)
    cur.close()
    return jsonify(_voto_publico(creado)), 201


@votos_bp.route("/pregunta/<int:id_pregunta>", methods=["GET"])
def votos_pregunta(id_pregunta):
    """
    Qué hace:
        Agrega los votos de una pregunta.
        total_votos = SUM(voto) → puntaje neto (+1 y -1).
        cantidad = COUNT(*) → cuántos votos hay, da igual el signo.

    Ruta y método:
        GET /votos/pregunta/<id_pregunta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_pregunta.

    Base de datos:
        Tabla votos: SELECT SUM y COUNT WHERE id_pregunta.
        No consulta si la pregunta existe. No escribe.

    Respuestas:
        200: {total_votos, cantidad} (0 y 0 si no hay filas o el id no existe).
    """
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT COALESCE(SUM(voto), 0) AS total_votos, COUNT(*) AS cantidad
        FROM votos
        WHERE id_pregunta = %s
        """,
        (id_pregunta,),
    )
    fila = cur.fetchone()
    cur.close()
    return jsonify({
        "total_votos": int(fila["total_votos"]),
        "cantidad": fila["cantidad"],
    }), 200


@votos_bp.route("/respuesta/<int:id_respuesta>", methods=["GET"])
def votos_respuesta(id_respuesta):
    """
    Qué hace:
        Igual que votos_pregunta, filtrando por id_respuesta.

    Ruta y método:
        GET /votos/respuesta/<id_respuesta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_respuesta.

    Base de datos:
        Tabla votos: SUM y COUNT WHERE id_respuesta. No escribe.

    Respuestas:
        200: {total_votos, cantidad}.
    """
    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT COALESCE(SUM(voto), 0) AS total_votos, COUNT(*) AS cantidad
        FROM votos
        WHERE id_respuesta = %s
        """,
        (id_respuesta,),
    )
    fila = cur.fetchone()
    cur.close()
    return jsonify({
        "total_votos": int(fila["total_votos"]),
        "cantidad": fila["cantidad"],
    }), 200


@votos_bp.route("/<int:id_voto>", methods=["DELETE"])
@token_requerido
def eliminar_voto(id_voto):
    """
    Qué hace:
        Quita un voto. Solo el usuario que lo creó (compara
        g.usuario["id"] con voto["id_usuario"]). Un admin no
        tiene permiso extra aquí.

    Ruta y método:
        DELETE /votos/<id_voto>

    Quién puede usarlo:
        JWT, y además el autor del voto (no "autor o admin").

    Entrada:
        URL: id_voto.

    Base de datos:
        votos: SELECT, DELETE, commit.

    Respuestas:
        200: {"mensaje": "Voto eliminado"}.
        403: el token no es del dueño del voto.
        404: id inexistente.
        401: JWT inválido.
    """
    cur = mysql.connection.cursor()
    voto = _buscar_voto(cur, id_voto)
    if not voto:
        cur.close()
        return jsonify({"error": "Voto no encontrado"}), 404

    # Solo el dueño del voto puede borrarlo
    if g.usuario.get("id") != voto["id_usuario"]:
        cur.close()
        return jsonify({"error": "No autorizado para eliminar este voto"}), 403

    cur.execute("DELETE FROM votos WHERE id = %s", (id_voto,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"mensaje": "Voto eliminado"}), 200
