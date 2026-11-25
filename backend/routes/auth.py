"""
Qué hace este archivo:
    Define el registro de cuentas nuevas y el inicio de sesión. El login
    es el único sitio que FIRMA el JWT (con Config.JWT_SECRET). El resto
    de rutas protegidas solo lo verifican (security.py).


Qué importa:
    - datetime: calcula la fecha de caducidad del token (exp).
    - jwt (PyJWT): jwt.encode para firmar el token.
    - flask: Blueprint, jsonify, request (body JSON).
    - werkzeug.security: generate_password_hash (guardar) y
      check_password_hash (comparar en el login).
    - config.Config: JWT_SECRET y JWT_ALGORITHM (mismos que security.py).
    - extensions.mysql: conexión a la tabla usuarios.
"""

import datetime

import jwt
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from extensions import mysql

# Prefijo /auth → las rutas quedan /auth/registro y /auth/login.
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _usuario_publico(fila):
    """
    Qué hace:
        Arma el JSON de usuario que sí se puede mostrar.
    """
    return {
        "id": fila["id"],
        "nombre_apellido": fila["nombre_apellido"],
        "correo": fila["correo"],
        "rol": fila["rol"],
        "fecha_registro": str(fila["fecha_registro"]),
        "avatar_url": fila.get("avatar_url"),
    }


@auth_bp.route("/registro", methods=["POST"])
def registro():
    """
    Respuestas:
        201: cuenta creada; JSON de _usuario_publico (sin token).
        400: falta algún campo obligatorio.
        409: ese correo ya está en la tabla.
    """
    datos = request.get_json(silent=True) or {}
    nombre_apellido = (datos.get("nombre_apellido") or "").strip()
    correo = (datos.get("correo") or "").strip()
    password = datos.get("password") or ""

    # Validación: los tres datos son obligatorios (password no se hace strip).
    if not nombre_apellido or not correo or not password:
        return jsonify({"error": "nombre_apellido, correo y password son obligatorios"}), 400

    if len(password) < 8 or not password.strip():
        return jsonify(error="La contraseña nueva debe tener al menos 8 caracteres"), 400

    cur = mysql.connection.cursor()
    # ¿Hay ya un usuario con ese correo? El correo debe ser único.
    cur.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "El correo ya está registrado"}), 409

    # Hash irreversible (Werkzeug, PBKDF2 por defecto). Así se guarda, no "1234".
    password_hash = generate_password_hash(password)
    cur.execute(
        "INSERT INTO usuarios (nombre_apellido, correo, password_hash, rol) VALUES (%s, %s, %s, 'estudiante') RETURNING id",
        (nombre_apellido, correo, password_hash),
    )
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    # Confirma el INSERT. Sin commit la fila no queda persistida.
    mysql.connection.commit()
    cur.execute(
        "SELECT id, nombre_apellido, correo, rol, fecha_registro FROM usuarios WHERE id = %s",
        (nuevo_id,),
    )
    usuario = cur.fetchone()
    cur.close()
    return jsonify(_usuario_publico(usuario)), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Qué hace:
        Comprueba correo + contraseña y, si coinciden, FIRMA un JWT.
        Flujo:
        1) Lee correo y password del body (si falta alguno → 400).
        2) SELECT * de usuarios por correo.
        3) Si no hay fila, o check_password_hash falla → 401
           (mismo mensaje para no revelar si el correo existe).
           check_password_hash compara la contraseña en claro del login
           con el password_hash guardado en el registro: recalcula el
           hash con la misma sal y mira si coinciden. Nunca se
           "descifra" el hash.
        4) Arma el payload del token:
           - id: para que otras rutas sepan quién es (g.usuario["id"])
           - correo
           - rol: "estudiante" o "admin" (solo_admin lo leerá después)
           - exp: ahora UTC + 24 horas; PyJWT rechaza el token después
        5) jwt.encode firma con JWT_SECRET y HS256 (config.py).
           Los otros servicios validan con la MISMA clave (security.py).
        6) Devuelve {token, usuario} con 200. El cliente debe enviar
           el token en: Authorization: Bearer <token>

    Ruta y método:
        POST /auth/login

    Quién puede usarlo:
        Público. No pide JWT; aquí se obtiene.

    Entrada:
        Body JSON: correo, password.

    Base de datos:
        Tabla usuarios: solo SELECT * WHERE correo = %s.
        No inserta, no actualiza, no elimina.

    Respuestas:
        200: token JWT + usuario público (sin password_hash).
        400: falta correo o password.
        401: correo inexistente o contraseña que no coincide con el hash.
    """
    datos = request.get_json(silent=True) or {}
    correo = (datos.get("correo") or "").strip()
    password = datos.get("password") or ""

    if not correo or not password:
        return jsonify({"error": "correo y password son obligatorios"}), 400

    cur = mysql.connection.cursor()
    # Trae también password_hash; hace falta para check_password_hash.
    cur.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
    usuario = cur.fetchone()
    cur.close()

    # Un solo 401 para "no existe" y "clave mala" (no filtrar cuentas).
    if not usuario or not check_password_hash(usuario["password_hash"], password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    if usuario.get("suspendido"):
        return jsonify({"error": "Cuenta suspendida"}), 403

    # Datos que viajarán dentro del JWT (luego serán g.usuario).
    payload = {
        "id": usuario["id"],
        "correo": usuario["correo"],
        "rol": usuario["rol"],
        "version_sesion": usuario.get("version_sesion", 0),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
    }
    # Firma el payload. Sin esta clave, security.py no podrá decodificarlo.
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
    return jsonify({"token": token, "usuario": _usuario_publico(usuario)}), 200
