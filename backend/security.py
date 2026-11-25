"""Autenticación compartida: firma JWT y autorización actual en PostgreSQL."""
from functools import wraps

import jwt
from flask import g, jsonify, request

from config import Config
from extensions import mysql


def _usuario_desde_token():
    # Los decoradores anidados reutilizan la identidad de esta petición.
    if "usuario" in g:
        return g.usuario, None
    partes = request.headers.get("Authorization", "").split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        return None, (jsonify({"error": "Token no enviado o formato inválido"}), 401)
    try:
        payload = jwt.decode(partes[1], Config.JWT_SECRET,
                             algorithms=[Config.JWT_ALGORITHM],
                             options={"require": ["exp", "id"]})
    except jwt.ExpiredSignatureError:
        return None, (jsonify({"error": "Token expirado"}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({"error": "Token inválido"}), 401)
    identificador = payload["id"]
    if type(identificador) is not int or not 0 < identificador <= 9223372036854775807:
        return None, (jsonify({"error": "Token inválido"}), 401)
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT id, correo, rol, suspendido, version_sesion FROM usuarios WHERE id = %s", (identificador,))
        usuario = cur.fetchone()
    if not usuario:
        return None, (jsonify({"error": "Usuario no disponible"}), 401)
    if usuario.get("suspendido"):
        return None, (jsonify({"error": "Cuenta suspendida"}), 401)
    if payload.get("version_sesion", 0) != usuario.get("version_sesion", 0):
        return None, (jsonify({"error": "Sesión revocada"}), 401)
    g.usuario = dict(usuario)
    return g.usuario, None


def token_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        _, error = _usuario_desde_token()
        if error:
            return error
        return f(*args, **kwargs)
    return decorada


def solo_admin(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        usuario, error = _usuario_desde_token()
        if error:
            return error
        if usuario["rol"] != "admin":
            return jsonify({"error": "Se requiere rol de administrador"}), 403
        return f(*args, **kwargs)
    return decorada
