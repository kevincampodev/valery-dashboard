from datetime import datetime
from ..extensions import db


class Documento(db.Model):
    __tablename__ = "documentos"

    id = db.Column(db.Integer, primary_key=True)
    nombre_original = db.Column(db.String(255), nullable=False)
    ruta = db.Column(db.String(255), nullable=False, unique=True)
    tipo = db.Column(db.String(10), nullable=False)
    subido_en = db.Column(db.DateTime, default=datetime.now)

    factura_id = db.Column(db.Integer, db.ForeignKey("facturas.id"))
    factura = db.relationship("Factura", back_populates="documentos")

    pago_id = db.Column(db.Integer, db.ForeignKey("pagos.id"))
    pago = db.relationship("Pago", back_populates="documentos")