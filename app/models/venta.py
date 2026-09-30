from datetime import datetime

from sqlalchemy import case

from ..extensions import db

CANALES = ["Minorista", "Mayorista"]
MEDIOS_VENTA = ["Efectivo", "Transferencia", "Datáfono", "Crédito", "Otro"]
MEDIOS_CONTACTO = ["Orgánico", "TikTok", "Voz a voz", "Otro"]


class Vendedora(db.Model):
    __tablename__ = "vendedoras"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False, unique=True)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    fecha_ingreso = db.Column(db.Date)
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    # Esquema de comisión
    tasa_comision_bp = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    meta_quincenal = db.Column(db.Integer)
    bono_meta = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    vende_mayorista = db.Column(db.Boolean, nullable=False, default=False, server_default="0")

    ventas = db.relationship("Venta", back_populates="vendedora")
    liquidaciones = db.relationship("Liquidacion", back_populates="vendedora")


class Venta(db.Model):
    __tablename__ = "ventas"
    __table_args__ = (
        db.CheckConstraint("valor > 0", name="valor_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    canal = db.Column(db.String(20), nullable=False)
    vendedora_id = db.Column(db.Integer, db.ForeignKey("vendedoras.id"))
    medio_pago = db.Column(db.String(20), nullable=False)
    valor = db.Column(db.Integer, nullable=False)
    prendas = db.Column(db.Integer)
    es_devolucion = db.Column(db.Boolean, default=False, nullable=False)
    medio_contacto = db.Column(db.String(20))
    origen = db.Column(db.String(10), nullable=False, default="manual", server_default="manual")
    creado_en = db.Column(db.DateTime, default=datetime.now)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"))

    vendedora = db.relationship("Vendedora", back_populates="ventas")
    cliente = db.relationship("Cliente", back_populates="ventas")
    lineas = db.relationship("LineaVenta", back_populates="venta", cascade="all, delete-orphan")

    @property
    def neto(self):
        return -self.valor if self.es_devolucion else self.valor


# Valor neto en SQL: resta las devoluciones. Úsalo con func.sum() para totales.
NETO_SQL = case((Venta.es_devolucion, -Venta.valor), else_=Venta.valor)