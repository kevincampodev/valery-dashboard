import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-cambiar")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB máximo por archivo subido
    EMPRESA_NOMBRE = os.getenv("EMPRESA_NOMBRE", "Mi Empresa SAS")