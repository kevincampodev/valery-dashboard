from ..extensions import db


class InversionPublicidad(db.Model):
    __tablename__ = "inversiones_publicidad"
    __table_args__ = (
        db.UniqueConstraint("mes", "canal", name="uq_inversiones_publicidad_mes_canal"),
        db.CheckConstraint("valor_diario >= 0", name="valor_no_negativo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Date, nullable=False)                 # siempre el día 1
    canal = db.Column(db.String(20), nullable=False, default="TikTok")
    valor_diario = db.Column(db.Integer, nullable=False)
    dias = db.Column(db.Integer)                             # vacío = todos los días del mes
    notas = db.Column(db.String(200))


class Parametro(db.Model):
    """Configuración del negocio que se edita desde la app (clave → valor)."""
    __tablename__ = "parametros"

    clave = db.Column(db.String(40), primary_key=True)
    valor = db.Column(db.String(200), nullable=False)

    @classmethod
    def obtener_int(cls, clave, defecto):
        parametro = db.session.get(cls, clave)
        return int(parametro.valor) if parametro else defecto

    @classmethod
    def guardar(cls, clave, valor):
        db.session.merge(cls(clave=clave, valor=str(valor)))