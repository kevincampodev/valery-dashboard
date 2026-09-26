from datetime import datetime
from ..extensions import db

FRECUENCIAS = ["mensual", "quincenal", "semanal"]
CATEGORIAS_GASTO = ["Arriendo", "Nómina", "Seguridad social", "Servicios", "Impuestos", "Préstamos", "Otro"]


class CuentaDinero(db.Model):
    __tablename__ = "cuentas_dinero"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(60), nullable=False, unique=True)
    saldo = db.Column(db.Integer, nullable=False, default=0)
    actualizado_en = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class GastoRecurrente(db.Model):
    __tablename__ = "gastos_recurrentes"
    __table_args__ = (db.CheckConstraint("valor > 0", name="valor_positivo"),)

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    categoria = db.Column(db.String(30), nullable=False)
    valor = db.Column(db.Integer, nullable=False)
    frecuencia = db.Column(db.String(12), nullable=False, default="mensual")
    dia = db.Column(db.Integer, nullable=False, default=1)  # mensual: 1-31 | semanal: 0=lunes..6=domingo
    activo = db.Column(db.Boolean, nullable=False, default=True)
    notas = db.Column(db.Text)


class AjusteTemporada(db.Model):
    __tablename__ = "ajustes_temporada"

    mes = db.Column(db.Integer, primary_key=True)             # 1 a 12
    factor_pct = db.Column(db.Integer, nullable=False, default=100)