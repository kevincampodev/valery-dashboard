import json
from datetime import datetime
from ..extensions import db


class Bitacora(db.Model):
    __tablename__ = "bitacora"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    accion = db.Column(db.String(10), nullable=False)       # crear | editar | eliminar
    tabla = db.Column(db.String(40), nullable=False, index=True)
    registro_id = db.Column(db.Integer)
    cambios = db.Column(db.Text)                             # JSON

    @property
    def detalle(self):
        return json.loads(self.cambios or "{}")