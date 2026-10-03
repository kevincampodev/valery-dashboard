import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-cambiar")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB máximo por archivo subido
    EMPRESA_NOMBRE = os.getenv("EMPRESA_NOMBRE", "Mi Empresa SAS")
    BACKUP_DIR = os.getenv("BACKUP_DIR")    # vacío = instance/backups
    DB_NAME = os.getenv("DB_NAME", "valery.db")
    WTF_CSRF_TIME_LIMIT = None              # el token dura lo que dure la sesión

    # Producción y sesiones
    ENTORNO = os.getenv("ENTORNO", "desarrollo")                     # "desarrollo" o "produccion"
    SESSION_COOKIE_HTTPONLY = True                                   # JavaScript no puede leer la cookie
    SESSION_COOKIE_SAMESITE = "Lax"                                  # otros sitios no pueden usar tu sesión
    SESSION_COOKIE_SECURE = os.getenv("COOKIES_SEGURAS", "0") == "1" # la cookie solo viaja por HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)                  # la sesión vence en 8 horas