"""
Qué hace este archivo:
    Centraliza la configuración de Flask: la conexión a la base de datos
    PostgreSQL (Supabase) y los parámetros para firmar y verificar tokens JWT.

    Los valores secretos NO se escriben aquí: se leen de variables de entorno.
    - En tu equipo: $env:DATABASE_URL="..."  (PowerShell) o export DATABASE_URL="..."
    - En Vercel: Settings → Environment Variables.
    Si falta alguna, la app no arranca y el error dice cuál es.
"""

import os


def _variable(nombre):
    """Lee una variable de entorno obligatoria o detiene el arranque con un mensaje claro."""
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return valor


class Config:
    # Cadena de conexión a PostgreSQL. En Supabase: botón Connect → "Transaction pooler"
    # (puerto 6543). Vercel solo usa IPv4 y la "Direct connection" de Supabase es solo
    # IPv6, por eso hay que usar el pooler.
    DATABASE_URL = _variable("DATABASE_URL")
    # Misma clave en todos los servicios para firmar y validar el JWT
    # El servicio de usuarios FIRMA el token en /auth/login con esta clave.
    # Los otros servicios lo VALIDAN (security.py) con la misma clave.
    # Si cada servicio tuviera una clave distinta, un token emitido en el
    # puerto 5000 sería "inválido" en 5001 y 5002: el foro dejaría de
    # reconocer al usuario entre microservicios.
    JWT_SECRET = _variable("JWT_SECRET")
    # Algoritmo de firma HMAC-SHA256. Debe coincidir al encode (auth) y al decode (security).
    JWT_ALGORITHM = "HS256"
