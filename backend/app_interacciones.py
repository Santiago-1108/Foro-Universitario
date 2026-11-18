"""
Qué hace este archivo:
    Punto de entrada del microservicio de interacciones. Crea la
    aplicación Flask, carga Config, engancha MySQL y registra los
    Blueprints de respuestas, comentarios y votos. Las rutas están en
    routes/respuestas.py, routes/comentarios.py y routes/votos.py.

A qué servicio pertenece:
    Servicio de interacciones (este archivo). Corre en su propio
    proceso; no arranca usuarios ni preguntas.

Qué importa:
    - flask.Flask: se crea la app con Flask(__name__).
    - config.Config: MYSQL_* para la BD y JWT_* para validar tokens
      emitidos por el servicio de usuarios (mismo JWT_SECRET).
    - extensions.mysql: init_app une esa instancia a esta app.
    - routes.respuestas.respuestas_bp: prefijo /respuestas.
    - routes.comentarios.comentarios_bp: prefijo /comentarios.
    - routes.votos.votos_bp: prefijo /votos.

Quién lo usa:
    Se ejecuta con: python app_interacciones.py
    El cliente llama a este servicio en el puerto 5002.
    Los otros app_*.py no importan este módulo.

Cómo se arma la app (orden de las líneas de abajo):
    1. Flask(__name__) crea el objeto app.
    2. from_object(Config) copia la configuración compartida a app.config.
    3. mysql.init_app(app) deja lista la conexión MySQL de extensions.py
       para las rutas (mysql.connection.cursor()).
    4. register_blueprint monta:
       - /respuestas/...  (respuestas_bp)
       - /comentarios/...  (comentarios_bp)
       - /votos/...  (votos_bp)
    5. if __name__ == "__main__": al ejecutar este archivo se levanta
       el servidor de desarrollo en el puerto 5002, debug=True.
"""

from flask import Flask

from config import Config
from extensions import mysql
from routes.comentarios import comentarios_bp
from routes.respuestas import respuestas_bp
from routes.votos import votos_bp

# 1) App Flask de este proceso (servicio de interacciones).
app = Flask(__name__)
# 2) Carga MYSQL_* y JWT_* desde config.py hacia app.config.
app.config.from_object(Config)
# 3) Engancha la instancia mysql de extensions.py a esta app (usa app.config).
mysql.init_app(app)

# 4) Respuestas a preguntas: prefijo /respuestas (routes/respuestas.py).
app.register_blueprint(respuestas_bp)
# 4) Comentarios: prefijo /comentarios (routes/comentarios.py).
app.register_blueprint(comentarios_bp)
# 4) Votos: prefijo /votos (routes/votos.py).
app.register_blueprint(votos_bp)

# 5) Solo al ejecutar "python app_interacciones.py": servidor en puerto 5002.
if __name__ == "__main__":
    app.run(port=5002, debug=True)
