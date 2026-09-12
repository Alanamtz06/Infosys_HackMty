"""Hash/verificacion de contraseñas para el login del repartidor.

Alcance de hackathon: sin JWT ni expiracion de sesion, el login devuelve el
perfil del usuario (id, username, vehicle_type) y el frontend lo guarda en su
estado global. Suficiente para la demo; no usar este esquema tal cual en
produccion (falta rotacion de token, rate limiting, etc).
"""

import bcrypt


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
