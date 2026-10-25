from datetime import date

from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from . import bp
from ...extensions import db
from ...models import Venta, InversionPublicidad, Parametro, NETO_SQL
from ...services.comisiones import CANAL_COMISIONABLE
from ...services.marketing import (meses_entre, inversion_del_mes, retorno_equilibrio, rentabilidad,
                                   REDES_PAUTA, PLATAFORMAS_PAUTA)
from ...services.permisos import ve_todo
from ...utils import a_pesos, a_bp, formato_bp, mes_desde_texto, nombre_mes

MARGEN_DEFECTO_BP = 5000


def _comision(venta):
    """Comisión que generó una venta (misma regla del módulo de comisiones)."""
    if venta.es_devolucion or venta.canal != CANAL_COMISIONABLE or not venta.vendedora:
        return 0
    return venta.valor * venta.vendedora.tasa_comision_bp // 10000


@bp.route("/")
def index():
    hoy = date.today()
    margen_bp = Parametro.obtener_int("margen_bruto_bp", MARGEN_DEFECTO_BP)
    pautas = {}
    for pauta in InversionPublicidad.query.order_by(InversionPublicidad.canal):
        pautas.setdefault(pauta.mes, []).append(pauta)

    por_mes = {}
    ventas_pauta = (Venta.query.options(joinedload(Venta.vendedora))
                    .filter(Venta.medio_contacto.in_(REDES_PAUTA)))
    for venta in ventas_pauta:
        acumulado = por_mes.setdefault(venta.fecha.replace(day=1),
                                       {"ventas": 0, "comisiones": 0, "por_red": dict.fromkeys(REDES_PAUTA, 0)})
        acumulado["ventas"] += venta.neto
        acumulado["comisiones"] += _comision(venta)
        acumulado["por_red"][venta.medio_contacto] += venta.neto

    mes_sql = func.strftime("%Y-%m", Venta.fecha)
    ventas_totales = dict(db.session.query(mes_sql, func.sum(NETO_SQL)).group_by(mes_sql).all())

    filas = []
    for mes in sorted(set(pautas) | set(por_mes)):
        if mes > hoy:
            continue
        pautas_mes = pautas.get(mes, [])
        datos = por_mes.get(mes, {"ventas": 0, "comisiones": 0, "por_red": dict.fromkeys(REDES_PAUTA, 0)})
        inversion = inversion_del_mes(pautas_mes, mes, hoy)
        fila = rentabilidad(datos["ventas"], inversion, datos["comisiones"], margen_bp)
        total_mes = ventas_totales.get(mes.strftime("%Y-%m")) or 0
        fila.update(mes=mes, etiqueta=nombre_mes(mes), pautas=pautas_mes, por_red=datos["por_red"],
                    participacion=round(datos["ventas"] * 100 / total_mes) if total_mes else 0)
        filas.append(fila)

    total = rentabilidad(sum(f["ventas"] for f in filas), sum(f["inversion"] for f in filas),
                         sum(f["comisiones"] for f in filas), margen_bp)
    grafica = {
        "etiquetas": [f["etiqueta"] for f in filas],
        "inversion": [f["inversion"] for f in filas],
        "ganancia": [f["ganancia_bruta"] - f["comisiones"] for f in filas],
        "resultado": [f["resultado"] for f in filas],
    }

    completo = ve_todo()
    if not completo:
        # Marketing no ve margen, ganancia, comisiones ni resultado: ni en pantalla ni en los datos de la página.
        privados = ("ganancia_bruta", "comisiones", "resultado", "estado", "participacion")
        for fila in filas + [total]:
            for clave in privados:
                fila.pop(clave, None)
        grafica = {"etiquetas": grafica["etiquetas"], "inversion": grafica["inversion"],
                   "ventas": [f["ventas"] for f in filas]}
        margen_bp = None
    por_red = {red: sum(f["por_red"][red] for f in filas) for red in REDES_PAUTA}
    return render_template("marketing/index.html", filas=filas, total=total, grafica=grafica, por_red=por_red,
                           redes=REDES_PAUTA, plataformas=PLATAFORMAS_PAUTA,
                           margen_bp=margen_bp, completo=completo,
                           equilibrio=retorno_equilibrio(margen_bp) if completo else None)


@bp.route("/margen", methods=["POST"])
def guardar_margen():
    margen = a_bp(request.form.get("margen"))
    if not 100 <= margen <= 9500:
        flash("El margen debe estar entre 1% y 95%.", "danger")
    else:
        Parametro.guardar("margen_bruto_bp", margen)
        db.session.commit()
        flash(f"Margen actualizado a {formato_bp(margen)}.", "success")
    return redirect(url_for("marketing.index"))


@bp.route("/pauta", methods=["POST"])
def guardar_pauta():
    f = request.form
    plataforma = f.get("plataforma")
    desde = mes_desde_texto(f.get("desde"))
    hasta = mes_desde_texto(f.get("hasta") or f.get("desde"))
    valor = a_pesos(f.get("valor_diario"))
    dias = f.get("dias", type=int)
    meses = meses_entre(desde, hasta)

    if plataforma not in PLATAFORMAS_PAUTA:
        flash("Elige la plataforma de la pauta.", "danger")
    elif not meses or len(meses) > 24:
        flash("Revisa el rango: 'hasta' no puede ser antes de 'desde' y el máximo es 24 meses.", "danger")
    elif valor <= 0:
        flash("El valor diario debe ser mayor a cero.", "danger")
    elif dias is not None and not 1 <= dias <= 31:
        flash("Los días deben estar entre 1 y 31 (o vacío para todo el mes).", "danger")
    else:
        for mes in meses:
            pauta = (InversionPublicidad.query.filter_by(mes=mes, canal=plataforma).first()
                     or InversionPublicidad(mes=mes, canal=plataforma))
            pauta.valor_diario = valor
            pauta.dias = dias
            db.session.add(pauta)
        db.session.commit()
        flash(f"Pauta de {plataforma} registrada para {len(meses)} mes(es).", "success")
    return redirect(url_for("marketing.index"))


@bp.route("/pauta/<int:id>/eliminar", methods=["POST"])
def eliminar_pauta(id):
    db.session.delete(db.get_or_404(InversionPublicidad, id))
    db.session.commit()
    flash("Pauta eliminada.", "info")
    return redirect(url_for("marketing.index"))