"""
Qué hace este archivo:
    Es el punto de entrada que Vercel ejecuta para toda la API (equivale al
    api/index.py de la guía de despliegue). Une en una sola aplicación los tres
    servicios del foro, cada uno montado en su propio prefijo:

        /api/usuarios       → app_usuarios.py       (cuentas y sesión)
        /api/foro           → app_preguntas.py      (preguntas y categorías)
        /api/interacciones  → app_interacciones.py  (respuestas, comentarios y votos)

    Es lo mismo que hace el proxy de Vite en vite.config.js durante el desarrollo:
    quita el prefijo y entrega la petición al servicio correcto. Por eso el
    frontend (services/api.js) no cambia.

    Los tres app_*.py NO se modifican: cada uno sigue siendo una app Flask
    independiente con sus propios Blueprints, y en tu equipo se siguen pudiendo
    levantar como tres procesos (puertos 5000, 5001 y 5002).

Cómo probarlo en local (necesita DATABASE_URL y JWT_SECRET definidas):
    flask --app api/index run
    http://127.0.0.1:5000/api/foro/categorias
"""

import os
import sys

from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# El backend vive en la carpeta backend/. La agregamos al path de Python para que
# sus imports (config, extensions, security, routes) funcionen igual que siempre.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app_interacciones import app as app_interacciones  # noqa: E402
from app_preguntas import app as app_preguntas  # noqa: E402
from app_usuarios import app as app_usuarios  # noqa: E402

# App principal que Vercel busca con el nombre "app". Lo que no coincida con
# ningún prefijo de abajo cae aquí y responde 404.
app = Flask(__name__)

# DispatcherMiddleware recorta el prefijo antes de llamar a cada servicio:
# /api/usuarios/auth/login llega a app_usuarios como /auth/login.
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app,
    {
        "/api/usuarios": app_usuarios,
        "/api/foro": app_preguntas,
        "/api/interacciones": app_interacciones,
    },
)
