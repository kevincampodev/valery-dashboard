from datetime import date

from flask import render_template, request
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...models import Factura, GastoRecurrente, Liquidacion
from ...services.proyeccion import proximos_pagos


@bp.route("/")
def index():
    hoy = date.today()
    dias = request.args.get("dias", 30, type=int)
    if dias not in (7, 15, 30, 60, 90):
        dias = 30

    items = proximos_pagos(
        hoy, dias,
        facturas=Factura.query.options(joinedload(Factura.proveedor), selectinload(Factura.aplicaciones)).all(),
        gastos=GastoRecurrente.query.filter_by(activo=True).all(),
        liquidaciones=Liquidacion.query.options(joinedload(Liquidacion.vendedora)).filter_by(estado="pendiente").all(),
    )
    vencidos = [i for i in items if i["fecha"] < hoy]
    proximos = [i for i in items if i["fecha"] >= hoy]

    return render_template("pagos/index.html", vencidos=vencidos, proximos=proximos, dias=dias, hoy=hoy,
                           total_vencido=sum(i["valor"] for i in vencidos),
                           total_proximo=sum(i["valor"] for i in proximos))