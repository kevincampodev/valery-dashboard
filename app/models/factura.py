from datetime import date, datetime
from ..extensions import db


class Factura(db.Model):
    __tablename__ = "facturas"
    __table_args__ = (
        db.UniqueConstraint("proveedor_id", "numero", name="uq_facturas_proveedor_numero"),
    )

    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"), nullable=False)
    numero = db.Column(db.String(40), nullable=False)
    fecha_emision = db.Column(db.Date, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)   # la que dice la factura
    fecha_pactada = db.Column(db.Date)                       # la que acordaron de verdad
    subtotal = db.Column(db.Integer, default=0)
    iva = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, nullable=False)
    etiqueta = db.Column(db.String(80))
    cufe = db.Column(db.String(120), unique=True)
    pagada_contado = db.Column(db.Boolean, default=False, nullable=False)
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    proveedor = db.relationship("Proveedor", back_populates="facturas")
    documentos = db.relationship("Documento", back_populates="factura",
                                 cascade="all, delete-orphan")
    aplicaciones = db.relationship("AplicacionPago", back_populates="factura")

    @property
    def fecha_limite(self):
        return self.fecha_pactada or self.fecha_vencimiento

    @property
    def abonado(self):
        return sum(a.valor for a in self.aplicaciones)

    @property
    def saldo(self):
        return 0 if self.pagada_contado else self.total - self.abonado

    @property
    def porcentaje_pagado(self):
        if self.saldo == 0:
            return 100
        return round(self.abonado * 100 / self.total)

    @property
    def dias_para_vencer(self):
        return (self.fecha_limite - date.today()).days

    @property
    def estado(self):
        if self.saldo == 0:
            return "pagada"
        if self.dias_para_vencer < 0:
            return "vencida"
        if self.dias_para_vencer <= 7:
            return "por vencer"
        return "al día"

    def __repr__(self):
        return f"<Factura {self.numero}>"