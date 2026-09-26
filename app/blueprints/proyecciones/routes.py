from datetime import date, timedelta

from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import (Factura, Venta, Liquidacion, CuentaDinero, GastoRecurrente, AjusteTemporada,
                       NETO_SQL, FRECUENCIAS, CATEGORIAS_GASTO)
from ...services.proyeccion import promedio_por_dia_semana, flujo_semanal
from ...utils import a_pesos, MESES

ESCENARIOS = {"pesimista": 80, "base": 100, "optimista": 120}


def tasa_comision_efectiva():
    """% real pagado en comisiones sobre ventas, según las últimas 12 liquidaciones (en puntos básicos)."""
    ultimas = Liquidacion.query.order_by(Liquidacion.inicio.desc()).limit(12).all()
    ventas = sum(l.ventas_netas for l in ultimas)
    return sum(l.total for l in ultimas) * 10000 // ventas if ventas > 0 else 0


@bp.route("/")
def index():
    hoy = date.today()
    escenario = request.args.get("escenario", "base")
    if escenario not in ESCENARIOS:
        escenario = "base"
    semanas = min(max(request.args.get("semanas", 12, type=int), 4), 26)

    filas_ventas = (db.session.query(Venta.fecha, func.sum(NETO_SQL))
                    .filter(Venta.fecha >= hoy - timedelta(weeks=8), Venta.fecha < hoy)
                    .group_by(Venta.fecha).all())
    ventas_por_fecha = {fecha: total or 0 for fecha, total in filas_ventas}

    facturas = Factura.query.options(joinedload(Factura.proveedor), selectinload(Factura.aplicaciones)).all()
    cuentas = CuentaDinero.query.order_by(CuentaDinero.nombre).all()
    saldo_inicial = sum(c.saldo for c in cuentas)

    filas = flujo_semanal(
        hoy=hoy,
        semanas=semanas,
        saldo_inicial=saldo_inicial,
        promedios=promedio_por_dia_semana(ventas_por_fecha, hoy),
        factores_mes={a.mes: a.factor_pct for a in AjusteTemporada.query.all()},
        escenario_pct=ESCENARIOS[escenario],
        facturas=facturas,
        gastos=GastoRecurrente.query.filter_by(activo=True).all(),
        liquidaciones=Liquidacion.query.filter_by(estado="pendiente").all(),
        tasa_comision_bp=tasa_comision_efectiva(),
    )

    grafica = {
        "etiquetas": [f["inicio"].strftime("%d/%m") for f in filas],
        "ventas": [f["ventas"] for f in filas],
        "salidas": [f["salidas"] for f in filas],
        "saldo": [f["saldo_final"] for f in filas],
    }

    return render_template(
        "proyecciones/index.html",
        filas=filas,
        grafica=grafica,
        cuentas=cuentas,
        saldo_inicial=saldo_inicial,
        escenario=escenario,
        escenarios=ESCENARIOS,
        semanas=semanas,
        primera_negativa=next((f for f in filas if f["saldo_final"] < 0), None),
        pocos_datos=len(ventas_por_fecha) < 14,
    )


# ---------- Configuración ----------

@bp.route("/configuracion")
def configuracion():
    return render_template(
        "proyecciones/configuracion.html",
        cuentas=CuentaDinero.query.order_by(CuentaDinero.nombre).all(),
        gastos=GastoRecurrente.query.order_by(GastoRecurrente.activo.desc(), GastoRecurrente.categoria).all(),
        factores={a.mes: a.factor_pct for a in AjusteTemporada.query.all()},
        meses=MESES,
        frecuencias=FRECUENCIAS,
        categorias=CATEGORIAS_GASTO,
        tasa_comision=tasa_comision_efectiva(),
    )


def _a_configuracion():
    return redirect(url_for("proyecciones.configuracion"))


@bp.route("/cuentas", methods=["POST"])
def crear_cuenta():
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("La cuenta necesita un nombre.", "danger")
        return _a_configuracion()
    db.session.add(CuentaDinero(nombre=nombre, saldo=a_pesos(request.form.get("saldo"))))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Ya existe una cuenta con ese nombre.", "danger")
    return _a_configuracion()


@bp.route("/cuentas/<int:id>", methods=["POST"])
def actualizar_cuenta(id):
    cuenta = db.get_or_404(CuentaDinero, id)
    texto = request.form.get("saldo", "")
    negativo = texto.strip().startswith("-")
    cuenta.saldo = -a_pesos(texto) if negativo else a_pesos(texto)
    db.session.commit()
    flash(f"Saldo de {cuenta.nombre} actualizado.", "success")
    return _a_configuracion()


@bp.route("/cuentas/<int:id>/eliminar", methods=["POST"])
def eliminar_cuenta(id):
    db.session.delete(db.get_or_404(CuentaDinero, id))
    db.session.commit()
    return _a_configuracion()


@bp.route("/gastos", methods=["POST"])
def crear_gasto():
    f = request.form
    valor = a_pesos(f.get("valor"))
    frecuencia = f.get("frecuencia")
    dia = f.get("dia", type=int) or 1
    limites = {"mensual": (1, 31), "semanal": (0, 6), "quincenal": (1, 31)}

    if not f.get("nombre", "").strip() or valor <= 0 or frecuencia not in FRECUENCIAS \
            or f.get("categoria") not in CATEGORIAS_GASTO:
        flash("Revisa el nombre, la categoría, la frecuencia y el valor del gasto.", "danger")
        return _a_configuracion()
    minimo, maximo = limites[frecuencia]
    if not minimo <= dia <= maximo:
        flash(f"Para frecuencia {frecuencia}, el día debe estar entre {minimo} y {maximo}.", "danger")
        return _a_configuracion()

    db.session.add(GastoRecurrente(nombre=f.get("nombre").strip(), categoria=f.get("categoria"),
                                   valor=valor, frecuencia=frecuencia, dia=dia))
    db.session.commit()
    flash("Gasto recurrente agregado.", "success")
    return _a_configuracion()


@bp.route("/gastos/<int:id>/estado", methods=["POST"])
def cambiar_estado_gasto(id):
    gasto = db.get_or_404(GastoRecurrente, id)
    gasto.activo = not gasto.activo
    db.session.commit()
    return _a_configuracion()


@bp.route("/gastos/<int:id>/eliminar", methods=["POST"])
def eliminar_gasto(id):
    db.session.delete(db.get_or_404(GastoRecurrente, id))
    db.session.commit()
    return _a_configuracion()


@bp.route("/temporada", methods=["POST"])
def guardar_temporada():
    for mes in range(1, 13):
        factor = request.form.get(f"mes_{mes}", type=int) or 100
        db.session.merge(AjusteTemporada(mes=mes, factor_pct=max(0, min(factor, 500))))
    db.session.commit()
    flash("Factores de temporada guardados.", "success")
    return _a_configuracion()