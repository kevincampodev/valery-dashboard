from datetime import date, datetime
from ..extensions import db


class Meta(db.Model):
    __tablename__ = "metas"
    __table_args__ = (
        db.UniqueConstraint("periodo", "canal", name="uq_metas_periodo_canal"),
        db.CheckConstraint("valor > 0", name="valor_positivo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    periodo = db.Column(db.Date, nullable=False)       # siempre el día 1 del mes
    canal = db.Column(db.String(20), nullable=False, default="Total")
    valor = db.Column(db.Integer, nullable=False)


class TramoIncentivo(db.Model):
    __tablename__ = "tramos_incentivo"

    id = db.Column(db.Integer, primary_key=True)
    cumplimiento_min = db.Column(db.Integer, nullable=False, unique=True)  # en %
    tasa_bp = db.Column(db.Integer, nullable=False, default=0)             # puntos básicos: 50 = 0,5%
    bono_fijo = db.Column(db.Integer, nullable=False, default=0)
    descripcion = db.Column(db.String(120))


class Objetivo(db.Model):
    __tablename__ = "objetivos"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_limite = db.Column(db.Date)
    proveedor_id = db.Column(db.Integer, db.ForeignKey("proveedores.id"))
    saldo_inicial = db.Column(db.Integer)
    progreso_manual = db.Column(db.Integer, nullable=False, default=0)
    completado = db.Column(db.Boolean, nullable=False, default=False)
    creado_en = db.Column(db.DateTime, default=datetime.now)

    proveedor = db.relationship("Proveedor")

    @property
    def progreso(self):
        if self.completado:
            return 100
        if self.proveedor and self.saldo_inicial:
            pagado = self.saldo_inicial - self.proveedor.deuda_total
            return max(0, min(100, round(pagado * 100 / self.saldo_inicial)))
        return self.progreso_manual

    @property
    def vencido(self):
        return bool(self.fecha_limite and self.progreso < 100 and self.fecha_limite < date.today())