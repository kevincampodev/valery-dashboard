from datetime import datetime
from ..extensions import db


class Liquidacion(db.Model):
    __tablename__ = "liquidaciones"
    __table_args__ = (
        db.UniqueConstraint("vendedora_id", "inicio", name="uq_liquidaciones_vendedora_inicio"),
    )

    id = db.Column(db.Integer, primary_key=True)
    vendedora_id = db.Column(db.Integer, db.ForeignKey("vendedoras.id"), nullable=False)
    inicio = db.Column(db.Date, nullable=False)
    fin = db.Column(db.Date, nullable=False)

    # "Foto" del cálculo al momento de liquidar
    ventas_netas = db.Column(db.Integer, nullable=False, default=0)
    tasa_bp = db.Column(db.Integer, nullable=False, default=0)
    meta = db.Column(db.Integer)
    comision = db.Column(db.Integer, nullable=False, default=0)
    bono = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)

    estado = db.Column(db.String(12), nullable=False, default="pendiente")  # pendiente | pagada
    fecha_pago = db.Column(db.Date)
    medio_pago = db.Column(db.String(30))
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    vendedora = db.relationship("Vendedora", back_populates="liquidaciones")
    documentos = db.relationship("Documento", back_populates="liquidacion",
                                 cascade="all, delete-orphan")

    @property
    def tiene_soporte(self):
        return bool(self.documentos)