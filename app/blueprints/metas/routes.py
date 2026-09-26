from datetime import date, timedelta

from flask import render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from . import bp
from ...extensions import db
from ...models import Meta, TramoIncentivo, Objetivo, Proveedor, Venta, CANALES
from ...services.metas import avance_meta, calcular_incentivo
from ...services.ventas import resumen_mes
from ...utils import a_pesos, a_fecha, a_bp, mes_desde_texto, rango_mes, nombre_mes

GRUPOS = ["Total"] + CANALES


def _volver():
    return redirect(url_for("metas.index", mes=request.form.get("mes")))


@bp.route("/")
def index():
    inicio, fin = rango_mes(mes_desde_texto(request.args.get("mes")))
    hoy = date.today()

    registros = Venta.query.filter(Venta.fecha.between(inicio, fin)).all()
    resumen = resumen_mes(registros, inicio, fin)
    vendido = {"Total": resumen["total"], **{c: resumen["por_canal"].get(c, 0) for c in CANALES}}

    metas = {m.canal: m.valor for m in Meta.query.filter_by(periodo=inicio)}
    avances = {canal: avance_meta(vendido[canal], valor, inicio, fin, hoy) for canal, valor in metas.items()}

    tramos = TramoIncentivo.query.order_by(TramoIncentivo.cumplimiento_min).all()
    incentivo = calcular_incentivo(resumen["total"], metas["Total"], tramos) if "Total" in metas else None

    return render_template(
        "metas/index.html",
        grupos=GRUPOS,
        metas=metas,
        avances=avances,
        tramos=tramos,
        incentivo=incentivo,
        objetivos=Objetivo.query.order_by(Objetivo.completado, Objetivo.fecha_limite).all(),
        proveedores=Proveedor.query.order_by(Proveedor.nombre).all(),
        titulo=nombre_mes(inicio),
        mes=inicio.strftime("%Y-%m"),
        anterior=(inicio - timedelta(days=1)).strftime("%Y-%m"),
        siguiente=(fin + timedelta(days=1)).strftime("%Y-%m"),
    )


@bp.route("/guardar", methods=["POST"])
def guardar_metas():
    inicio = mes_desde_texto(request.form.get("mes"))
    for canal in GRUPOS:
        valor = a_pesos(request.form.get(f"meta_{canal}"))
        meta = Meta.query.filter_by(periodo=inicio, canal=canal).first()
        if valor > 0:
            if meta:
                meta.valor = valor
            else:
                db.session.add(Meta(periodo=inicio, canal=canal, valor=valor))
        elif meta:
            db.session.delete(meta)
    db.session.commit()
    flash("Metas guardadas.", "success")
    return _volver()


@bp.route("/tramos", methods=["POST"])
def agregar_tramo():
    cumplimiento = request.form.get("cumplimiento_min", type=int)
    if not cumplimiento or not 1 <= cumplimiento <= 300:
        flash("El cumplimiento mínimo debe estar entre 1% y 300%.", "danger")
        return _volver()

    db.session.add(TramoIncentivo(
        cumplimiento_min=cumplimiento,
        tasa_bp=a_bp(request.form.get("tasa")),
        bono_fijo=a_pesos(request.form.get("bono_fijo")),
        descripcion=request.form.get("descripcion", "").strip() or None,
    ))
    try:
        db.session.commit()
        flash("Tramo agregado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"Ya existe un tramo desde {cumplimiento}%.", "danger")
    return _volver()


@bp.route("/tramos/<int:id>/eliminar", methods=["POST"])
def eliminar_tramo(id):
    db.session.delete(db.get_or_404(TramoIncentivo, id))
    db.session.commit()
    flash("Tramo eliminado.", "info")
    return _volver()


@bp.route("/objetivos", methods=["POST"])
def crear_objetivo():
    titulo = request.form.get("titulo", "").strip()
    if not titulo:
        flash("El objetivo necesita un título.", "danger")
        return _volver()

    objetivo = Objetivo(
        titulo=titulo,
        descripcion=request.form.get("descripcion", "").strip() or None,
        fecha_limite=a_fecha(request.form.get("fecha_limite")),
    )
    proveedor_id = request.form.get("proveedor_id", type=int)
    if proveedor_id:
        proveedor = db.get_or_404(Proveedor, proveedor_id)
        objetivo.proveedor = proveedor
        objetivo.saldo_inicial = proveedor.deuda_total
        if not objetivo.saldo_inicial:
            flash(f"{proveedor.nombre} no tiene deuda; el objetivo quedará al 100%.", "warning")

    db.session.add(objetivo)
    db.session.commit()
    flash("Objetivo creado.", "success")
    return _volver()


@bp.route("/objetivos/<int:id>/progreso", methods=["POST"])
def actualizar_objetivo(id):
    objetivo = db.get_or_404(Objetivo, id)
    if "completar" in request.form:
        objetivo.completado = not objetivo.completado
    else:
        progreso = request.form.get("progreso", type=int) or 0
        objetivo.progreso_manual = max(0, min(100, progreso))
    db.session.commit()
    return _volver()


@bp.route("/objetivos/<int:id>/eliminar", methods=["POST"])
def eliminar_objetivo(id):
    db.session.delete(db.get_or_404(Objetivo, id))
    db.session.commit()
    flash("Objetivo eliminado.", "info")
    return _volver()