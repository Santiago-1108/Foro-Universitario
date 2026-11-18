"""
Qué hace este archivo:
    Punto de entrada del microservicio de preguntas. Crea la aplicación
    Flask, carga Config, engancha MySQL y registra los Blueprints de
    preguntas y categorías. No define rutas aquí: están en
    routes/preguntas.py y routes/categorias.py.

A qué servicio pertenece:
    Servicio de preguntas (este archivo). Es independiente del de
    usuarios (puerto 5000) y del de interacciones (puerto 5002).

Qué importa:
    - flask.Flask: se crea la app con Flask(__name__).
    - config.Config: misma clase que los otros servicios (incluye
      JWT_SECRET, necesario para que security.py acepte tokens firmados
      en el login del puerto 5000).
    - extensions.mysql: misma idea de instancia única; cada proceso
      llama init_app sobre SU propia app.
    - routes.preguntas.preguntas_bp: Blueprint con prefijo /preguntas.
    - routes.categorias.categorias_bp: Blueprint con prefijo /categorias.

Quién lo usa:
    Se ejecuta con: python app_preguntas.py
    El cliente llama a este servicio en el puerto 5001.
    app_usuarios.py y app_interacciones.py no importan este archivo.

Cómo se arma la app (orden de las líneas de abajo):
    1. Flask(__name__) crea el objeto app.
    2. from_object(Config) copia MYSQL_* y JWT_* a app.config.
    3. mysql.init_app(app) conecta extensions.mysql con esta app; las
       rutas harán consultas con mysql.connection.cursor().
    4. register_blueprint monta:
       - /preguntas/...  (preguntas_bp)
       - /categorias/...  (categorias_bp)
    5. if __name__ == "__main__": al ejecutar este archivo se levanta
       el servidor de desarrollo en el puerto 5001, debug=True.
"""

from flask import Flask

from config import Config
from extensions import mysql
from routes.categorias import categorias_bp
from routes.preguntas import preguntas_bp

# 1) App Flask de este proceso (servicio de preguntas).
app = Flask(__name__)
# 2) Carga MYSQL_* y JWT_* desde config.py hacia app.config.
app.config.from_object(Config)
# 3) Engancha la instancia mysql de extensions.py a esta app (usa app.config).
mysql.init_app(app)

# 4) CRUD de preguntas: prefijo /preguntas (routes/preguntas.py).
app.register_blueprint(preguntas_bp)
# 4) CRUD de categorías: prefijo /categorias (routes/categorias.py).
app.register_blueprint(categorias_bp)

# 5) Solo al ejecutar "python app_preguntas.py": servidor en puerto 5001.
if __name__ == "__main__":
    app.run(port=5001, debug=True)
