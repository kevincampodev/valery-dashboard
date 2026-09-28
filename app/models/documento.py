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

    liquidacion_id = db.Column(db.Integer, db.ForeignKey("liquidaciones.id"))
    liquidacion = db.relationship("Liquidacion", back_populates="documentos")


    @property
    def vinculo(self):
        """(tipo, descripción, endpoint, parámetros) para enlazar al registro dueño del archivo."""
        if self.factura:
            return ("Factura", f"{self.factura.proveedor.nombre} · {self.factura.numero}",
                    "deudas.detalle", {"id": self.factura_id})
        if self.pago:
            return ("Abono", f"{self.pago.proveedor.nombre} · {self.pago.fecha:%d/%m/%Y}",
                    "abonos.index", {"proveedor": self.pago.proveedor_id})
        if self.liquidacion:
            return ("Comisión", f"{self.liquidacion.vendedora.nombre} · {self.liquidacion.inicio:%d/%m/%Y}",
                    "comisiones.detalle", {"id": self.liquidacion_id})
        return ("Sin vínculo", "", None, {})