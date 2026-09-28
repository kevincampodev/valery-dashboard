import os
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