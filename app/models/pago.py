from datetime import date, datetime
from ..extensions import db

MEDIOS_PAGO = ["Transferencia", "Efectivo", "Consignación", "Cheque", "Tarjeta"]


class Pago(db.Model):
    __tablename__ = "pagos"

    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    valor = db.Column(db.Integer, nullable=False)
    medio = db.Column(db.String(30), nullable=False)
    referencia = db.Column(db.String(80))
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    proveedor = db.relationship("Proveedor", back_populates="pagos")
    aplicaciones = db.relationship("AplicacionPago", back_populates="pago",
                                   cascade="all, delete-orphan")
    documentos = db.relationship("Documento", back_populates="pago",
                                 cascade="all, delete-orphan")

    @property
    def aplicado(self):
        return sum(a.valor for a in self.aplicaciones)

    @property
    def sin_aplicar(self):
        return self.valor - self.aplicado


class AplicacionPago(db.Model):
    __tablename__ = "aplicaciones_pago"
    __table_args__ = (
        db.UniqueConstraint("pago_id", "factura_id", name="uq_aplicaciones_pago_pago_factura"),
    )

    id = db.Column(db.Integer, primary_key=True)
    pago_id = db.Column(db.Integer, db.ForeignKey("pagos.id"), nullable=False)
    factura_id = db.Column(db.Integer, db.ForeignKey("facturas.id"), nullable=False)
    valor = db.Column(db.Integer, nullable=False)

    pago = db.relationship("Pago", back_populates="aplicaciones")
    factura = db.relationship("Factura", back_populates="aplicaciones")