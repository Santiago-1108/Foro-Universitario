"""
Cómo se arma la app (orden de las líneas de abajo):
    1. Flask(__name__) crea el objeto app vacío.
    2. from_object(Config) copia al app.config los atributos de config.py
       (MYSQL_HOST, MYSQL_DB, JWT_SECRET, etc.).
    3. mysql.init_app(app) une la instancia de extensions.py con esta app.
       Flask-MySQLdb lee entonces app.config para saber a qué MySQL
       conectarse. Las rutas usarán mysql.connection.cursor().
"""

from flask import Flask

from config import Config 
from extensions import mysql
from routes.auth import auth_bp
from routes.usuarios import usuarios_bp
from routes.notificaciones import notificaciones_bp
from routes.moderacion import moderacion_bp
from routes.mensajes import mensajes_bp

# 1) App Flask de este proceso (servicio de usuarios).
app = Flask(__name__)
# 2) Carga MYSQL_* y JWT_* desde config.py hacia app.config.
app.config.from_object(Config)
# 3) Engancha la instancia mysql de extensions.py a esta app (usa app.config).
mysql.init_app(app)
# 4) Rutas públicas de registro/login: prefijo /auth (routes/auth.py).
app.register_blueprint(auth_bp)
# 4) Rutas de perfil/listado de usuarios: prefijo /usuarios (routes/usuarios.py).
app.register_blueprint(usuarios_bp)
app.register_blueprint(notificaciones_bp)
app.register_blueprint(moderacion_bp)
app.register_blueprint(mensajes_bp)

# 5) Solo al ejecutar "python app_usuarios.py": servidor en puerto 5000.
if __name__ == "__main__":
    app.run(port=5000, debug=False)
