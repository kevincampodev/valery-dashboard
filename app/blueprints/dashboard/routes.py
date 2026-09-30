from datetime import date

from flask import render_template
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import Factura, Pago, Meta, Venta, Cliente, NETO_SQL
from ...models.marketing import InversionPublicidad
from ...services.indicadores import (resumen_deudas, deuda_por_proveedor, vencimientos_por_semana,
                                     clientes_sin_comprar)
from ...services.metas import avance_meta
from ...utils import rango_mes

DIAS_SIN_COMPRA = 45
RETORNO_EQUILIBRIO = 2   # con 50% de margen, cada $1 de pauta debe vender al menos $2 para no perder


@bp.route("/")
def index():
    hoy = date.today()
    facturas = Factura.query.options(
        joinedload(Factura.proveedor),
        selectinload(Factura.aplicaciones),
    ).all()
    pagos_mes = Pago.query.filter(Pago.fecha >= hoy.replace(day=1)).all()

    # Ventas y meta del mes
    inicio_mes, fin_mes = rango_mes(hoy.replace(day=1))
    ventas_mes = Venta.query.filter(Venta.fecha.between(inicio_mes, fin_mes)).all()
    vendido_mes = sum(v.neto for v in ventas_mes)
    meta_mes = Meta.query.filter_by(periodo=inicio_mes, canal="Total").first()
    avance_mes = avance_meta(vendido_mes, meta_mes.valor, inicio_mes, fin_mes, hoy) if meta_mes else None

    # Ventas del mes por canal
    canales_mes = {"Minorista": 0, "Mayorista": 0}
    for v in ventas_mes:
        canales_mes[v.canal] = canales_mes.get(v.canal, 0) + v.neto

    # TikTok del mes
    ventas_tiktok = sum(v.neto for v in ventas_mes if v.medio_contacto == "TikTok")
    pauta = InversionPublicidad.query.filter_by(mes=inicio_mes, canal="TikTok").first()
    dias_pauta = min(pauta.dias or hoy.day, hoy.day) if pauta else 0
    inversion = pauta.valor_diario * dias_pauta if pauta else 0
    tiktok = {
        "ventas": ventas_tiktok,
        "inversion": inversion,
        "retorno": ventas_tiktok / inversion if inversion else None,
        "equilibrio": RETORNO_EQUILIBRIO,
    }

    # Mayoristas que no han vuelto
    activos = {c.id: c for c in Cliente.query.filter_by(activo=True)}
    compras = (db.session.query(Venta.cliente_id, func.max(Venta.fecha), func.sum(NETO_SQL))
               .filter(Venta.cliente_id.isnot(None)).group_by(Venta.cliente_id).all())
    clientes_frios = clientes_sin_comprar(
        [(activos[cid], ultima, total) for cid, ultima, total in compras if cid in activos],
        hoy, DIAS_SIN_COMPRA,
    )

    # Gráficas de deuda
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
        canales_mes=canales_mes,
        tiktok=tiktok,
        clientes_frios=clientes_frios,
        hay_clientes=bool(activos),
        dias_sin_compra=DIAS_SIN_COMPRA,
    )