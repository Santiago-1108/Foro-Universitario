"""
Qué hace este archivo:
    Ofrece un único objeto de conexión a la base de datos (el objeto mysql)
    para que todas las rutas compartan la misma forma de abrir conexión,
    sin crear una distinta en cada módulo.

    OJO con el nombre: el objeto se sigue llamando "mysql" solo para no tener
    que cambiar las rutas, pero ahora conecta con PostgreSQL (Supabase) usando
    psycopg2. Las rutas siguen escribiendo mysql.connection.cursor(),
    mysql.connection.commit() y fila["columna"], igual que antes.

A qué servicio pertenece:
    Es código compartido por los tres microservicios
    (app_usuarios.py, app_preguntas.py, app_interacciones.py).

Qué importa:
    - psycopg2: driver de PostgreSQL. RealDictCursor hace que cada fila sea
      un diccionario (fila["id"]), como el DictCursor que se usaba con MySQL.

Quién lo usa:
    - Cada app llama mysql.init_app(app) después de
      app.config.from_object(Config). Ahí se registra el cierre automático.
    - Las rutas importan mysql y usan mysql.connection.cursor() para
      ejecutar SQL (routes/auth.py, usuarios.py, preguntas.py,
      categorias.py, respuestas.py, comentarios.py, votos.py).
    - security.py consulta el usuario y su rol actual en PostgreSQL.
"""

import psycopg2
import psycopg2.extras
from flask import current_app, g, jsonify, request
from psycopg2 import errors
from werkzeug.exceptions import HTTPException

# Identificador de contrato, no revela configuración ni credenciales.
REVISION_API = "comunidades-multimedia-1"


def estado_api():
    return jsonify(revision=REVISION_API, modulos=sorted(current_app.blueprints))


def error_http(error):
    mensajes = {400: "Solicitud inválida", 401: "Autenticación requerida",
                403: "No tienes permisos", 404: "Ruta o recurso no encontrado",
                405: "Método HTTP no permitido", 422: "Datos no válidos",
                500: "Error interno del servidor", 502: "Servicio no disponible",
                503: "Servicio temporalmente no disponible"}
    # Conservar cabeceras como Allow de los errores 405.
    respuesta = error.get_response()
    respuesta.set_data(current_app.json.dumps({"error": mensajes.get(error.code, "Error HTTP" )}))
    respuesta.content_type = "application/json"
    return respuesta


class ConexionPostgres:
    """Abre UNA conexión por petición (la primera vez que se pide) y la cierra al terminar."""

    def init_app(self, app):
        # Al terminar cada petición Flask llama a _cerrar: así no quedan
        # conexiones abiertas (importante en Vercel, donde cada petición es corta).
        app.config["MAX_CONTENT_LENGTH"] = 32768
        app.teardown_appcontext(self._cerrar)
        app.before_request(validar_json)
        app.after_request(no_cache_privado)
        app.add_url_rule('/estado-api', view_func=estado_api, methods=['GET'])
        app.register_error_handler(HTTPException, error_http)
        app.register_error_handler(psycopg2.IntegrityError, error_integridad)
        app.register_error_handler(errors.InsufficientPrivilege, lambda _: (jsonify(error="Participación no autorizada o permisos insuficientes"), 403))
        app.register_error_handler(psycopg2.DataError, error_datos)
        app.register_error_handler(psycopg2.OperationalError, error_conexion)
        app.register_error_handler(413, lambda _: (jsonify(error="Solicitud demasiado grande"), 413))

    @property
    def connection(self):
        # g es el espacio de datos de la petición actual: guarda ahí la conexión
        # para que todas las consultas de esa petición usen la misma.
        if "conexion_db" not in g:
            g.conexion_db = psycopg2.connect(
                current_app.config["DATABASE_URL"],
                cursor_factory=psycopg2.extras.RealDictCursor,
                connect_timeout=10,
            )
        return g.conexion_db

    def _cerrar(self, error=None):
        conexion = g.pop("conexion_db", None)
        if conexion is not None:
            # Si hubo un error sin commit, al cerrar se descarta (rollback).
            conexion.close()


# Instancia única; cada app la inicializa con init_app
mysql = ConexionPostgres()


# Validación compartida de los campos usados por las rutas actuales.
# Los campos obligatorios y permisos específicos se comprueban en cada ruta.
LIMITES_TEXTO = {"nombre_apellido": 120, "correo": 120, "password": 256,
                 "rol": 20, "titulo": 200, "contenido": 2000,
                 "nombre": 80, "descripcion": 2000}


def validar_json():
    if request.method not in ("POST", "PUT", "PATCH"):
        return None
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "Se requiere un objeto JSON válido"}), 400
    for campo, limite in LIMITES_TEXTO.items():
        if campo not in datos:
            continue
        valor = datos[campo]
        if (not isinstance(valor, str) or "\x00" in valor or len(valor) > limite
                or (campo not in ("descripcion", "password") and not valor.strip() and not (campo=="contenido" and (getattr(request,"path","")=="/preguntas" or getattr(request,"path","").startswith("/preguntas/"))))):
            return jsonify({"error": f"{campo} inválido (máximo {limite} caracteres)"}), 400
    for campo in ("id_categoria", "id_pregunta", "id_respuesta"):
        if campo in datos and datos[campo] is not None:
            valor = datos[campo]
            if type(valor) is not int or not 0 < valor <= 9223372036854775807:
                return jsonify({"error": f"{campo} debe ser un entero positivo"}), 400
    if "correo" in datos:
        correo = datos["correo"].strip()
        if correo.count("@") != 1 or any(c.isspace() for c in correo) or not all(correo.split("@")):
            return jsonify({"error": "Correo inválido"}), 400
    return None


def _rollback():
    conexion = g.get("conexion_db")
    if conexion is not None and not conexion.closed:
        try:
            conexion.rollback()
        except psycopg2.Error:
            pass


def error_integridad(error):
    _rollback()
    if isinstance(error, errors.UniqueViolation):
        mensaje = "El registro ya existe o entra en conflicto con uno existente"
    elif isinstance(error, errors.ForeignKeyViolation):
        mensaje = "La operación entra en conflicto con registros relacionados"
    else:
        mensaje = "La operación incumple una restricción de datos"
    return jsonify({"error": mensaje}), 409


def error_datos(error):
    _rollback()
    return jsonify({"error": "Datos inválidos"}), 400


def error_conexion(error):
    _rollback()
    return jsonify({"error": "Base de datos temporalmente no disponible"}), 503


def no_cache_privado(respuesta):
    if request.headers.get("Authorization") or request.method != "GET":
        respuesta.headers["Cache-Control"] = "private, no-store"
    if request.path == '/estado-api':
        respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["X-Foro-Revision"] = REVISION_API
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.vary.add("Authorization")
    return respuesta
