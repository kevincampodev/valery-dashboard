from datetime import date

from flask import render_template
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...models import Factura, Pago, Meta, Venta
from ...services.indicadores import resumen_deudas, deuda_por_proveedor, vencimientos_por_semana
from ...services.metas import avance_meta
from ...utils import rango_mes


@bp.route("/")
def index():
    hoy = date.today()
    facturas = Factura.query.options(
        joinedload(Factura.proveedor),
        selectinload(Factura.aplicaciones),
    ).all()

    pagos_mes = Pago.query.filter(Pago.fecha >= hoy.replace(day=1)).all()

    inicio_mes, fin_mes = rango_mes(hoy.replace(day=1))
    meta_mes = Meta.query.filter_by(periodo=inicio_mes, canal="Total").first()
    vendido_mes = sum(v.neto for v in Venta.query.filter(Venta.fecha.between(inicio_mes, fin_mes)))
    avance_mes = avance_meta(vendido_mes, meta_mes.valor, inicio_mes, fin_mes, hoy) if meta_mes else None
    etiquetas, valores = vencimientos_por_semana(facturas, hoy)
    por_proveedor = deuda_por_proveedor(facturas)

    return render_template(
        "dashboard/index.html",
        hoy=hoy,
        resumen=resumen_deudas(facturas),
        abonado_mes=sum(p.valor for p in pagos_mes),
        n_abonos_mes=len(pagos_mes),
        grafica_semanas={"etiquetas": etiquetas, "valores": valores},
        grafica_proveedores={"nombres": [n for n, _ in por_proveedor],
                             "valores": [v for _, v in por_proveedor]},
        ultimos_abonos=Pago.query.order_by(Pago.fecha.desc(), Pago.id.desc()).limit(5).all(),
        avance_mes=avance_mes,
        vendido_mes=vendido_mes,
    )