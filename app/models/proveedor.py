from datetime import datetime
from ..extensions import db


class Proveedor(db.Model):
    __tablename__ = "proveedores"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False, unique=True)
    nit = db.Column(db.String(20), unique=True)
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(120))
    dias_credito = db.Column(db.Integer, default=0)
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    facturas = db.relationship("Factura", back_populates="proveedor",
                               order_by="Factura.fecha_emision")
    pagos = db.relationship("Pago", back_populates="proveedor")

    @property
    def deuda_total(self):
        return sum(f.saldo for f in self.facturas)

    def __repr__(self):
        return f"<Proveedor {self.nombre}>"