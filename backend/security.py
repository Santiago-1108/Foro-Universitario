"""
A qué servicio pertenece:
    Es código compartido. Lo importan las rutas de los tres microservicios
    (usuarios, preguntas e interacciones). El login que emite el token
    está en routes/auth.py (servicio de usuarios).

Qué importa:
    - functools.wraps: el decorador no pierde el nombre de la función original.
    - jwt (PyJWT): decodifica y verifica la firma.
    - flask.g, jsonify, request: request para el header; g para guardar
      el usuario de esta petición; jsonify para errores JSON.
    - config.Config: JWT_SECRET y JWT_ALGORITHM (deben ser los mismos
      con los que routes/auth.py firmó el token).

Quién lo usa:
    - token_requerido: routes/usuarios.py, preguntas.py, categorias.py,
      respuestas.py, comentarios.py, votos.py.
    - solo_admin: routes/usuarios.py (rutas exclusivas de administrador).
    - routes/auth.py no lo usa: registro y login son públicos.

Cómo se valida el token (paso a paso):
    1. Header Authorization
       El cliente debe enviar: Authorization: Bearer <token>
       Se parte el texto por espacios. Tienen que quedar exactamente
       dos piezas y la primera debe ser la palabra "Bearer".
       Si falta el header, está vacío o el formato no es ese → 401.
    2. Extraer el token
       La segunda pieza es el JWT (tres partes separadas por puntos:
       header.payload.firma).
    3. Decodificación y firma
       jwt.decode usa Config.JWT_SECRET y Config.JWT_ALGORITHM (HS256).
       Recalcula la firma. Si alguien alteró el payload o usó otra clave,
       falla con InvalidTokenError → 401 "Token inválido".
    4. Expiración
       En el login, auth.py mete "exp" (ahora + 24 horas). PyJWT rechaza
       el token si esa fecha ya pasó → ExpiredSignatureError → 401
       "Token expirado".
    5. Rol (solo en solo_admin)
       Tras un decode correcto, se mira payload["rol"]. Si no es "admin"
       → 403 (el token es válido, pero no alcanza el permiso).
    6. g.usuario
       Si no hubo error, se asigna g.usuario = payload.
       g es el almacén de Flask para ESTA petición HTTP (no se comparte
       entre usuarios). Cuando una ruta lee g.usuario, está leyendo el
       diccionario del JWT, no una fila de MySQL. Suele traer:
         - id: id del usuario en la tabla usuarios
         - correo: correo con el que inició sesión
         - rol: "estudiante" o "admin" (así estaba en el momento del login)
         - exp: fecha de caducidad (timestamp)
       Este archivo no consulta la base de datos. Si el usuario se borró
       o le cambiaron el rol después del login, el token sigue diciendo
       lo que se firmó hasta que expire.
"""

from functools import wraps

import jwt
from flask import g, jsonify, request

from config import Config


def _usuario_desde_token():
    """
    Qué hace:
        Función interna (el guion bajo _ indica que no se usa desde las
        rutas). Lee el JWT, lo valida y devuelve el payload o un error.
        token_requerido y solo_admin la llaman para no repetir la lógica.

    Ruta y método:
        No es un endpoint. No tiene Blueprint ni url_prefix.

    Quién puede usarlo:
        Solo este módulo. El cliente no la llama: llega a ella a través
        de un decorador en una ruta protegida.

    Entrada:
        Header HTTP Authorization con el formato: Bearer <token>
        No lee body ni parámetros de URL.

    Base de datos:
        No consulta, no inserta, no actualiza ni elimina. Solo verifica
        la firma del token con Config.JWT_SECRET.

    Respuestas:
        No responde sola al cliente. Devuelve una tupla (payload, error):
        - (payload, None): token correcto; payload es el diccionario JWT.
        - (None, (jsonify(...), 401)): el decorador reenvía ese 401.
          Casos: header ausente/mal formado, token caducado, token inválido.
    """
    encabezado = request.headers.get("Authorization", "")
    partes = encabezado.split()

    # Validación del formato: debe ser exactamente "Bearer" + el token.
    if len(partes) != 2 or partes[0] != "Bearer":
        return None, (jsonify({"error": "Token no enviado o formato inválido"}), 401)

    token = partes[1]
    try:
        # Verifica firma (JWT_SECRET) y, si existe, el campo exp.
        payload = jwt.decode(
            token,
            Config.JWT_SECRET,
            algorithms=[Config.JWT_ALGORITHM],
        )
        return payload, None
    except jwt.ExpiredSignatureError:
        # El campo exp del payload ya quedó en el pasado.
        return None, (jsonify({"error": "Token expirado"}), 401)
    except jwt.InvalidTokenError:
        # Firma incorrecta, token corrupto, algoritmo no permitido, etc.
        return None, (jsonify({"error": "Token inválido"}), 401)


def token_requerido(f):
    """
    Qué hace:
        Decorador: exige un JWT válido antes de ejecutar la vista.
        Si el token sirve, guarda el payload en g.usuario y llama a la ruta.

    Ruta y método:
        No es un endpoint. Se coloca encima de rutas que sí lo son, por
        ejemplo @preguntas_bp.route(...) y luego @token_requerido.
        La URL completa es la del Blueprint de esa ruta, no de este archivo.

    Quién puede usarlo:
        Cualquier usuario autenticado (estudiante o admin) con un token
        aún vigente. No comprueba el rol.

    Entrada:
        La misma que _usuario_desde_token: header Authorization Bearer.
        La vista original recibe sus args/kwargs (id de URL, body, etc.).

    Base de datos:
        No toca la base. La ruta decorada sí puede consultar o escribir
        usando mysql de extensions.py.

    Respuestas:
        - 401: token ausente, mal formado, expirado o inválido
          (lo genera _usuario_desde_token).
        - Si el token es válido, no responde: deja que la vista decida
          (200, 201, 403 de negocio, 404, etc.).
    """

    @wraps(f)
    def decorada(*args, **kwargs):
        payload, error = _usuario_desde_token()
        if error:
            return error
        # g.usuario queda disponible en la vista: g.usuario["id"], ["rol"], ["correo"].
        g.usuario = payload
        return f(*args, **kwargs)

    return decorada


def solo_admin(f):
    """
    Qué hace:
        Decorador más estricto: primero valida el JWT y después exige
        que payload["rol"] sea exactamente "admin".

    Ruta y método:
        No es un endpoint. En este proyecto se usa en routes/usuarios.py
        junto con token_requerido en algunas rutas de administración.

    Quién puede usarlo:
        Solo quien tenga rol "admin" dentro del token. Un estudiante
        con token válido recibe 403, no 401.

    Entrada:
        Header Authorization: Bearer <token>. El rol se lee del payload,
        no de un campo del body.

    Base de datos:
        No consulta la tabla usuarios en este momento. El rol es el que
        se firmó en el login (routes/auth.py).

    Respuestas:
        - 401: mismos fallos de token que token_requerido.
        - 403: token válido pero rol distinto de "admin".
        - Si es admin, no responde: ejecuta la vista y esa vista elige
          el código HTTP de éxito o de error de negocio.
    """

    @wraps(f)
    def decorada(*args, **kwargs):
        payload, error = _usuario_desde_token()
        if error:
            return error
        # Token bueno, pero el permiso no alcanza.
        if payload.get("rol") != "admin":
            return jsonify({"error": "Se requiere rol de administrador"}), 403
        g.usuario = payload
        return f(*args, **kwargs)

    return decorada
