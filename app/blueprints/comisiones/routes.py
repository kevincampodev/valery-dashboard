from datetime import date, timedelta

from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import func

from . import bp
from ...extensions import db
from ...models import Vendedora, Venta, Liquidacion, Documento, MEDIOS_PAGO, NETO_SQL
from ...services.archivos import guardar_archivo
from ...services.comisiones import quincena_de, etiqueta_quincena, calcular_comision
from ...utils import a_pesos, a_fecha, a_bp, formato_pesos


def _leer_quincena(texto):
    try:
        return quincena_de(date.fromisoformat(texto))
    except (TypeError, ValueError):
        return quincena_de(date.today())


def ventas_por_vendedora(inicio, fin):
    filas = (db.session.query(Venta.vendedora_id, func.sum(NETO_SQL))
             .filter(Venta.fecha.between(inicio, fin), Venta.vendedora_id.isnot(None))
             .group_by(Venta.vendedora_id).all())
    return {vendedora_id: total or 0 for vendedora_id, total in filas}


def _liquidar(vendedora, inicio, fin, ventas_netas):
    liq = Liquidacion.query.filter_by(vendedora_id=vendedora.id, inicio=inicio).first()
    if liq and liq.estado == "pagada":
        return None
    if not liq:
        liq = Liquidacion(vendedora=vendedora, inicio=inicio, fin=fin)
        db.session.add(liq)

    calculo = calcular_comision(ventas_netas, vendedora.tasa_comision_bp,
                                vendedora.meta_quincenal, vendedora.bono_meta)
    liq.ventas_netas = ventas_netas
    liq.tasa_bp = vendedora.tasa_comision_bp
    liq.meta = vendedora.meta_quincenal
    liq.comision = calculo["comision"]
    liq.bono = calculo["bono"]
    liq.total = calculo["total"]
    return liq


@bp.route("/")
def index():
    inicio, fin = _leer_quincena(request.args.get("q"))
    ventas = ventas_por_vendedora(inicio, fin)
    liquidaciones = {l.vendedora_id: l for l in Liquidacion.query.filter_by(inicio=inicio)}

    filas = []
    for v in Vendedora.query.order_by(Vendedora.nombre).all():
        liq = liquidaciones.get(v.id)
        vendido = ventas.get(v.id, 0)
        if not v.activa and not liq and not vendido:
            continue
        filas.append({
            "vendedora": v,
            "ventas": vendido,
            "calculo": calcular_comision(vendido, v.tasa_comision_bp, v.meta_quincenal, v.bono_meta),
            "liquidacion": liq,
            "desactualizada": bool(liq and liq.estado == "pendiente" and liq.ventas_netas != vendido),
        })

    return render_template(
        "comisiones/index.html",
        filas=filas,
        inicio=inicio,
        titulo=etiqueta_quincena(inicio, fin),
        terminada=fin < date.today(),
        por_pagar=sum(l.total for l in liquidaciones.values() if l.estado == "pendiente"),
        pagado=sum(l.total for l in liquidaciones.values() if l.estado == "pagada"),
        anterior=quincena_de(inicio - timedelta(days=1))[0].isoformat(),
        siguiente=(fin + timedelta(days=1)).isoformat(),
    )


@bp.route("/liquidar", methods=["POST"])
def liquidar():
    inicio, fin = _leer_quincena(request.form.get("q"))
    ventas = ventas_por_vendedora(inicio, fin)
    vendedora_id = request.form.get("vendedora_id", type=int)

    if vendedora_id:
        vendedoras = [db.get_or_404(Vendedora, vendedora_id)]
    else:
        vendedoras = [v for v in Vendedora.query.all() if v.activa or ventas.get(v.id)]

    liquidadas = [liq for v in vendedoras if (liq := _liquidar(v, inicio, fin, ventas.get(v.id, 0)))]
    db.session.commit()

    if fin >= date.today():
        flash("Ojo: la quincena aún no termina. Podrás recalcular mientras no esté pagada.", "warning")
    flash(f"{len(liquidadas)} liquidación(es) calculadas.", "success")

    if vendedora_id and liquidadas:
        return redirect(url_for("comisiones.detalle", id=liquidadas[0].id))
    return redirect(url_for("comisiones.index", q=inicio.isoformat()))


@bp.route("/esquemas", methods=["GET", "POST"])
def esquemas():
    vendedoras = Vendedora.query.filter_by(activa=True).order_by(Vendedora.nombre).all()
    if request.method == "POST":
        for v in vendedoras:
            v.tasa_comision_bp = a_bp(request.form.get(f"tasa_{v.id}"))
            v.meta_quincenal = a_pesos(request.form.get(f"meta_{v.id}")) or None
            v.bono_meta = a_pesos(request.form.get(f"bono_{v.id}"))
        db.session.commit()
        flash("Esquemas guardados. Las liquidaciones pendientes se actualizan al recalcular.", "success")
        return redirect(url_for("comisiones.index"))
    return render_template("comisiones/esquemas.html", vendedoras=vendedoras)


@bp.route("/liquidacion/<int:id>")
def detalle(id):
    liq = db.get_or_404(Liquidacion, id)
    por_dia = (db.session.query(Venta.fecha, func.sum(NETO_SQL))
               .filter(Venta.vendedora_id == liq.vendedora_id, Venta.fecha.between(liq.inicio, liq.fin))
               .group_by(Venta.fecha).order_by(Venta.fecha).all())
    return render_template("comisiones/detalle.html", liq=liq, por_dia=por_dia,
                           titulo=etiqueta_quincena(liq.inicio, liq.fin),
                           medios=MEDIOS_PAGO, hoy=date.today())


def _guardar_soportes(liq):
    guardados = 0
    for archivo in request.files.getlist("soportes"):
        if archivo and archivo.filename:
            try:
                ruta, tipo = guardar_archivo(archivo, "soportes")
            except ValueError as e:
                flash(str(e), "warning")
                continue
            liq.documentos.append(Documento(nombre_original=archivo.filename, ruta=ruta, tipo=tipo))
            guardados += 1
    return guardados


@bp.route("/liquidacion/<int:id>/pagar", methods=["POST"])
def pagar(id):
    liq = db.get_or_404(Liquidacion, id)
    if liq.estado == "pagada":
        flash("Esta liquidación ya estaba pagada.", "info")
        return redirect(url_for("comisiones.detalle", id=id))

    medio = request.form.get("medio")
    if medio not in MEDIOS_PAGO:
        flash("Selecciona un medio de pago.", "danger")
        return redirect(url_for("comisiones.detalle", id=id))

    liq.estado = "pagada"
    liq.fecha_pago = a_fecha(request.form.get("fecha_pago")) or date.today()
    liq.medio_pago = medio
    liq.notas = request.form.get("notas", "").strip() or None
    soportes = _guardar_soportes(liq)
    db.session.commit()

    flash(f"Pago de {formato_pesos(liq.total)} a {liq.vendedora.nombre} registrado.", "success")
    if not soportes:
        flash("Recuerda subir el comprobante firmado.", "warning")
    return redirect(url_for("comisiones.detalle", id=id))


@bp.route("/liquidacion/<int:id>/soporte", methods=["POST"])
def subir_soporte(id):
    liq = db.get_or_404(Liquidacion, id)
    if _guardar_soportes(liq):
        db.session.commit()
        flash("Soporte firmado guardado.", "success")
    else:
        flash("No se seleccionó ningún archivo.", "warning")
    return redirect(url_for("comisiones.detalle", id=id))


@bp.route("/liquidacion/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    liq = db.get_or_404(Liquidacion, id)
    if liq.estado == "pagada":
        flash("No se puede eliminar una liquidación pagada.", "danger")
        return redirect(url_for("comisiones.detalle", id=id))
    inicio = liq.inicio.isoformat()
    db.session.delete(liq)
    db.session.commit()
    flash("Liquidación eliminada.", "info")
    return redirect(url_for("comisiones.index", q=inicio))


@bp.route("/vendedora/<int:id>")
def historial(id):
    vendedora = db.get_or_404(Vendedora, id)
    liquidaciones = (Liquidacion.query.filter_by(vendedora_id=id)
                     .order_by(Liquidacion.inicio.desc()).all())
    anio = date.today().year
    return render_template(
        "comisiones/historial.html",
        vendedora=vendedora,
        liquidaciones=liquidaciones,
        etiqueta=etiqueta_quincena,
        pagado_anio=sum(l.total for l in liquidaciones if l.estado == "pagada" and l.inicio.year == anio),
        sin_soporte=sum(1 for l in liquidaciones if l.estado == "pagada" and not l.tiene_soporte),
        anio=anio,
    )