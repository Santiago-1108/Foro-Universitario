"""
Qué importa:
    - flask: Blueprint, g (usuario del token), jsonify, request.
    - werkzeug.security.generate_password_hash: al crear o al cambiar
      contraseña (el login que COMPARA el hash está en routes/auth.py).
    - extensions.mysql: conexión MySQL (tabla usuarios).
    - security.token_requerido: JWT válido → g.usuario.
    - security.solo_admin: JWT + rol "admin".

Quién lo usa:
    Cliente autenticado contra el puerto 5000, rutas /usuarios...
    El token lo emite POST /auth/login (routes/auth.py).
"""

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from extensions import mysql
from security import solo_admin, token_requerido

# Prefijo /usuarios → GET/POST /usuarios y GET/PUT/DELETE /usuarios/<id>
usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

ROLES_VALIDOS = ("estudiante", "docente", "admin")


def _usuario_publico(fila):
    """
    Qué hace:
        Copia a un dict los campos públicos (sin password_hash).

    """
    return {
        "id": fila["id"],
        "nombre_apellido": fila["nombre_apellido"],
        "correo": fila["correo"],
        "rol": fila["rol"],
        "fecha_registro": str(fila["fecha_registro"]),
    }


def _buscar_usuario(cur, id_usuario):
    """
    Qué hace:
        Busca un usuario por id usando el cursor que ya abrió la vista.
    Entrada:
        cur: cursor MySQL ya abierto.
        id_usuario: id numérico (viene de la URL en las vistas).
    Base de datos:
        Tabla usuarios: SELECT de campos públicos WHERE id = %s.
    """
    cur.execute(
        "SELECT id, nombre_apellido, correo, rol, fecha_registro FROM usuarios WHERE id = %s",
        (id_usuario,),
    )
    return cur.fetchone()


@usuarios_bp.route("", methods=["GET"])
@token_requerido
def listar_usuarios():
    """
    Qué hace:
        Devuelve todos los usuarios (sin hashes de contraseña).

    Base de datos:
        Tabla usuarios: SELECT de campos públicos (toda la tabla).
        No escribe.

    Respuestas:
        200: lista JSON de usuarios.
        401: lo responde token_requerido si el JWT falla (security.py).
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre_apellido, correo, rol, fecha_registro FROM usuarios")
    filas = cur.fetchall()
    cur.close()
    return jsonify([_usuario_publico(f) for f in filas]), 200


@usuarios_bp.route("/<int:id_usuario>", methods=["GET"])
@token_requerido
def obtener_usuario(id_usuario):
    """
    Qué hace:
        Devuelve un usuario por id, o 404 si no está.

    Ruta y método:
        GET /usuarios/<id_usuario>

    Quién puede usarlo:
        JWT. Cualquier autenticado puede ver cualquier id
        (no se comprueba que sea "el dueño").

    Entrada:
        URL: id_usuario (entero).

    Base de datos:
        Tabla usuarios: SELECT por id (_buscar_usuario). No escribe.

    Respuestas:
        200: usuario público.
        404: no hay fila con ese id.
        401: token inválido/ausente (token_requerido).
    """
    cur = mysql.connection.cursor()
    usuario = _buscar_usuario(cur, id_usuario)
    cur.close()
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(_usuario_publico(usuario)), 200


@usuarios_bp.route("", methods=["POST"])
@token_requerido
@solo_admin
def crear_usuario():
    """
    Qué hace:
        Alta de usuario hecha por un admin (puede elegir el rol).
        El registro público está en POST /auth/registro y siempre
        deja rol 'estudiante'.

    Ruta y método:
        POST /usuarios

    Quién puede usarlo:
        Solo admin. Decoradores: token_requerido y solo_admin
        (security.py). El token se valida dos veces; solo_admin
        exige payload["rol"] == "admin".

    Entrada:
        Body JSON: nombre_apellido, correo, password, rol
        (rol debe estar en ROLES_VALIDOS).

    Base de datos:
        Tabla usuarios:
        - SELECT por correo (duplicado → 409)
        - INSERT con password hasheada y el rol indicado
        - commit
        - SELECT del insertado

    Respuestas:
        201: usuario creado.
        400: faltan campos o rol no está en ROLES_VALIDOS.
        409: correo ya registrado.
        401: JWT malo (token_requerido / solo_admin).
        403: token válido pero no es admin (solo_admin).
    """
    datos = request.get_json(silent=True) or {}
    nombre_apellido = (datos.get("nombre_apellido") or "").strip()
    correo = (datos.get("correo") or "").strip()
    password = datos.get("password") or ""
    rol = (datos.get("rol") or "").strip()

    if not nombre_apellido or not correo or not password or not rol:
        return jsonify({"error": "nombre_apellido, correo, password y rol son obligatorios"}), 400
    if rol not in ROLES_VALIDOS:
        return jsonify({"error": "rol inválido"}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "El correo ya está registrado"}), 409

    cur.execute(
        "INSERT INTO usuarios (nombre_apellido, correo, password_hash, rol) VALUES (%s, %s, %s, %s) RETURNING id",
        (nombre_apellido, correo, generate_password_hash(password), rol),
    )
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    usuario = _buscar_usuario(cur, nuevo_id)
    cur.close()
    return jsonify(_usuario_publico(usuario)), 201


@usuarios_bp.route("/<int:id_usuario>", methods=["PUT"])
@token_requerido
def actualizar_usuario(id_usuario):
    """
    Qué hace:
        Actualiza nombre, correo, opcionalmente contraseña y, si es
        admin, el rol. Si no mandan un campo, se deja el valor actual.

    Ruta y método:
        PUT /usuarios/<id_usuario>

    Quién puede usarlo:
        JWT, y además autor o admin: g.usuario["id"] debe ser el
        id_usuario de la URL, o g.usuario["rol"] == "admin".
        Cambiar el rol: solo admin (un estudiante no puede
        autoascenderse).

    Entrada:
        URL: id_usuario.
        Body JSON opcional: nombre_apellido, correo, password, rol.
        El usuario sale de g.usuario (token_requerido → security.py).

    Base de datos:
        Tabla usuarios:
        - SELECT por id
        - SELECT de correo duplicado si el correo cambia
        - UPDATE (con o sin password_hash nuevo)
        - commit
        - SELECT del registro ya actualizado

    Respuestas:
        200: usuario actualizado.
        400: rol enviado pero no está en ROLES_VALIDOS.
        403: ni dueño ni admin; o no-admin intentando cambiar rol.
        404: id inexistente.
        409: el correo nuevo ya lo tiene otro usuario.
        401: JWT inválido (token_requerido).
    """
    # Permiso: el id del token o un admin. Si no, ni se toca la BD.
    es_admin = g.usuario.get("rol") == "admin"
    if g.usuario.get("id") != id_usuario and not es_admin:
        return jsonify({"error": "No autorizado para modificar este usuario"}), 403

    cur = mysql.connection.cursor()
    usuario = _buscar_usuario(cur, id_usuario)
    if not usuario:
        cur.close()
        return jsonify({"error": "Usuario no encontrado"}), 404

    datos = request.get_json(silent=True) or {}
    nombre_apellido = (datos.get("nombre_apellido") or usuario["nombre_apellido"]).strip()
    correo = (datos.get("correo") or usuario["correo"]).strip()
    rol = usuario["rol"]
    if "rol" in datos:
        if not es_admin:
            cur.close()
            return jsonify({"error": "Solo un admin puede cambiar el rol"}), 403
        rol = (datos.get("rol") or "").strip()
        if rol not in ROLES_VALIDOS:
            cur.close()
            return jsonify({"error": "rol inválido"}), 400

    if correo != usuario["correo"]:
        cur.execute("SELECT id FROM usuarios WHERE correo = %s AND id <> %s", (correo, id_usuario))
        if cur.fetchone():
            cur.close()
            return jsonify({"error": "El correo ya está registrado"}), 409

    if datos.get("password"):
        cur.execute(
            "UPDATE usuarios SET nombre_apellido = %s, correo = %s, rol = %s, password_hash = %s WHERE id = %s",
            (nombre_apellido, correo, rol, generate_password_hash(datos["password"]), id_usuario),
        )
    else:
        cur.execute(
            "UPDATE usuarios SET nombre_apellido = %s, correo = %s, rol = %s WHERE id = %s",
            (nombre_apellido, correo, rol, id_usuario),
        )
    mysql.connection.commit()
    actualizado = _buscar_usuario(cur, id_usuario)
    cur.close()
    return jsonify(_usuario_publico(actualizado)), 200


@usuarios_bp.route("/<int:id_usuario>", methods=["DELETE"])
@token_requerido
@solo_admin
def eliminar_usuario(id_usuario):
    """
    Qué hace:
        Borra un usuario por id. Solo un administrador.

    Ruta y método:
        DELETE /usuarios/<id_usuario>

    Quién puede usarlo:
        Solo admin (token_requerido + solo_admin de security.py).
        El dueño de la cuenta no puede borrarse si no es admin.

    Entrada:
        URL: id_usuario.

    Base de datos:
        Tabla usuarios:
        - SELECT por id (si no hay → 404, no se borra nada)
        - DELETE WHERE id = %s
        - commit

    Respuestas:
        200: {"mensaje": "Usuario eliminado"}.
        404: id inexistente.
        401: JWT inválido.
        403: autenticado pero no admin.
    """
    cur = mysql.connection.cursor()
    usuario = _buscar_usuario(cur, id_usuario)
    if not usuario:
        cur.close()
        return jsonify({"error": "Usuario no encontrado"}), 404

    cur.execute("DELETE FROM usuarios WHERE id = %s", (id_usuario,))
    mysql.connection.commit()
    cur.close()
    return jsonify({"mensaje": "Usuario eliminado"}), 200
