from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(40), nullable=False, unique=True)     # con el que inicia sesión, en minúsculas
    nombre = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    debe_cambiar_password = db.Column(db.Boolean, nullable=False, default=True)

    totp_secreto = db.Column(db.String(32))                              # semilla del 2FA
    totp_activo = db.Column(db.Boolean, nullable=False, default=False)

    intentos_fallidos = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_hasta = db.Column(db.DateTime)
    version_sesion = db.Column(db.Integer, nullable=False, default=1)
    ultimo_acceso = db.Column(db.DateTime)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    def fijar_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.version_sesion = (self.version_sesion or 0) + 1   # cierra las sesiones abiertas en otros equipos

    def verificar_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.activo

    def get_id(self):
        return f"{self.id}-{self.version_sesion}"


class EventoAcceso(db.Model):
    """Registro de cada intento de inicio de sesión, exitoso o fallido."""
    __tablename__ = "eventos_acceso"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    usuario = db.Column(db.String(40))          # lo que escribieron, aunque ese usuario no exista
    ip = db.Column(db.String(45))
    exito = db.Column(db.Boolean, nullable=False)
    motivo = db.Column(db.String(80))
    navegador = db.Column(db.String(200))