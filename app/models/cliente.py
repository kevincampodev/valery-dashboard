from datetime import datetime
from ..extensions import db


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    documento = db.Column(db.String(20), unique=True)      # cédula o NIT
    telefono = db.Column(db.String(30))
    ciudad = db.Column(db.String(60))
    notas = db.Column(db.Text)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    ventas = db.relationship("Venta", back_populates="cliente")


class LineaVenta(db.Model):
    __tablename__ = "lineas_venta"
    __table_args__ = (
        db.CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        db.CheckConstraint("precio_unitario > 0", name="precio_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id"), nullable=False)
    referencia = db.Column(db.String(30), nullable=False, index=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Integer, nullable=False)

    venta = db.relationship("Venta", back_populates="lineas")

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario