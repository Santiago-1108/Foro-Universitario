"""Votos idempotentes sobre preguntas y respuestas. POST establece -1/0/+1;
GET consulta totales y DELETE conserva la ruta histórica por id de voto.
Las restricciones UNIQUE existentes arbitran solicitudes concurrentes.
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido, _usuario_desde_token

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
    """Establece el voto (+1/-1) o lo cancela (0), de forma idempotente."""
    datos = request.get_json()
    voto = datos.get("voto")
    id_pregunta = datos.get("id_pregunta")
    id_respuesta = datos.get("id_respuesta")
    if (id_pregunta is None) == (id_respuesta is None):
        return jsonify({"error": "Debe enviar exactamente un destino"}), 400
    if type(voto) is not int or voto not in (-1, 0, 1):
        return jsonify({"error": "voto inválido; debe ser -1, 0 o 1"}), 400
    # Los nombres SQL son constantes internas, nunca datos del cliente.
    tabla, columna, destino = ("preguntas", "id_pregunta", id_pregunta) if id_pregunta is not None else ("respuestas", "id_respuesta", id_respuesta)
    id_usuario = g.usuario["id"]
    with mysql.connection.cursor() as cur:
        sql_destino = ("SELECT p.id FROM preguntas p WHERE p.id=%s AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) FOR UPDATE OF p"
                       if tabla == "preguntas" else "SELECT p.id FROM preguntas p JOIN respuestas r ON r.id_pregunta=p.id WHERE r.id=%s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario) FOR UPDATE OF p")
        cur.execute(sql_destino, (destino,id_usuario) if tabla=="preguntas" else (destino,id_usuario,id_usuario))
        if not cur.fetchone():
            return jsonify({"error": "Destino no encontrado"}), 404
        if voto == 0:
            cur.execute(f"DELETE FROM votos WHERE id_usuario = %s AND {columna} = %s", (id_usuario, destino))
            resultado = {"id": None, "id_usuario": id_usuario, "id_pregunta": id_pregunta, "id_respuesta": id_respuesta, "voto": 0}
        else:
            cur.execute(f"""INSERT INTO votos (id_usuario, {columna}, voto)
                VALUES (%s, %s, %s) ON CONFLICT (id_usuario, {columna})
                DO UPDATE SET voto = EXCLUDED.voto
                RETURNING id, id_usuario, id_pregunta, id_respuesta, voto""",
                (id_usuario, destino, voto))
            resultado = _voto_publico(cur.fetchone())
        cur.execute(f"SELECT COALESCE(SUM(voto), 0) AS total_votos, COUNT(*) AS cantidad FROM votos WHERE {columna} = %s", (destino,))
        resultado.update(cur.fetchone())
        mysql.connection.commit()
    return jsonify(resultado), 200


def _consultar_votos(columna, destino):
    identidad = None
    if request.headers.get("Authorization"):
        identidad, error = _usuario_desde_token()
        if error:
            return error
    with mysql.connection.cursor() as cur:
        uid = identidad["id"] if identidad else None
        sql = ("SELECT id FROM preguntas WHERE id=%s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario)" if columna == "id_pregunta" else
               "SELECT r.id FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta WHERE r.id=%s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario)")
        cur.execute(sql,(destino,uid) if columna=="id_pregunta" else (destino,uid,uid))
        if not cur.fetchone():
            return jsonify(error="Destino no encontrado"),404
        cur.execute(f"SELECT COALESCE(SUM(voto),0) AS total_votos, COUNT(*) AS cantidad FROM votos WHERE {columna}=%s", (destino,))
        resultado = dict(cur.fetchone(), mi_voto=0)
        if identidad:
            cur.execute(f"SELECT voto FROM votos WHERE {columna}=%s AND id_usuario=%s", (destino,identidad["id"]))
            fila = cur.fetchone()
            resultado["mi_voto"] = fila["voto"] if fila else 0
        return jsonify(resultado),200


@votos_bp.route("/pregunta/<int:id_pregunta>", methods=["GET"])
def votos_pregunta(id_pregunta):
    return _consultar_votos("id_pregunta",id_pregunta)


@votos_bp.route("/respuesta/<int:id_respuesta>", methods=["GET"])
def votos_respuesta(id_respuesta):
    return _consultar_votos("id_respuesta",id_respuesta)


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
