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
    - security.py no usa esta conexión: el JWT se valida en memoria,
      sin consultar la tabla usuarios.
"""

import psycopg2
import psycopg2.extras
from flask import current_app, g


class ConexionPostgres:
    """Abre UNA conexión por petición (la primera vez que se pide) y la cierra al terminar."""

    def init_app(self, app):
        # Al terminar cada petición Flask llama a _cerrar: así no quedan
        # conexiones abiertas (importante en Vercel, donde cada petición es corta).
        app.teardown_appcontext(self._cerrar)

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
