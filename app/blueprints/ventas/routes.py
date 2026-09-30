from datetime import date, timedelta

from flask import render_template, request, redirect, url_for, flash, abort
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from . import bp
from ...extensions import db
from ...models import Venta, Vendedora, CANALES, MEDIOS_VENTA, MEDIOS_CONTACTO
from ...services.ventas import resumen_mes
from ...utils import a_pesos, a_fecha, formato_pesos, mes_desde_texto, rango_mes, nombre_mes


@bp.route("/")
def index():
    inicio, fin = rango_mes(mes_desde_texto(request.args.get("mes")))
    registros = (Venta.query.options(joinedload(Venta.vendedora))
                 .filter(Venta.fecha.between(inicio, fin)).all())
    resumen = resumen_mes(registros, inicio, fin)

    grafica = {
        "etiquetas": [d.strftime("%d") for d in resumen["por_dia"]],
        "series": {c: [d["canales"].get(c, 0) for d in resumen["por_dia"].values()] for c in CANALES},
    }

    return render_template(
        "ventas/index.html",
        r=resumen,
        grafica=grafica,
        canales=CANALES,
        titulo=nombre_mes(inicio),
        anterior=(inicio - timedelta(days=1)).strftime("%Y-%m"),
        siguiente=(fin + timedelta(days=1)).strftime("%Y-%m"),
        hoy=date.today(),
    )


@bp.route("/dia/<fecha>", methods=["GET", "POST"])
def dia(fecha):
    try:
        fecha_venta = date.fromisoformat(fecha)
    except ValueError:
        abort(404)

    vendedoras = Vendedora.query.filter_by(activa=True).order_by(Vendedora.nombre).all()
    ids_validos = {v.id for v in vendedoras}

    if request.method == "POST":
        f = request.form
        filas = zip(f.getlist("canal"), f.getlist("vendedora_id"), f.getlist("medio_pago"),
                    f.getlist("tipo"), f.getlist("valor"), f.getlist("prendas"), f.getlist("medio_contacto"))

        nuevas, errores = [], []
        for n, (canal, vendedora_id, medio, tipo, valor, prendas, contacto) in enumerate(filas, start=1):
            valor = a_pesos(valor)
            if valor <= 0:
                continue  # fila vacía: se ignora
            vendedora_id = int(vendedora_id) if vendedora_id else None
            if contacto not in MEDIOS_CONTACTO:
                errores.append(f"Fila {n}: falta el medio de contacto.")
                continue
            if canal not in CANALES or medio not in MEDIOS_VENTA or (vendedora_id and vendedora_id not in ids_validos):
                errores.append(f"Fila {n}: datos inválidos.")
                continue
            nuevas.append(Venta(
                fecha=fecha_venta, canal=canal, vendedora_id=vendedora_id, medio_pago=medio,
                valor=valor, prendas=int(prendas) if prendas.isdigit() else None, medio_contacto=contacto,
                es_devolucion=(tipo == "devolucion"),
            ))

        if errores:
            for e in errores:
                flash(e, "danger")
        elif not nuevas:
            flash("No había filas con valor para guardar.", "warning")
        else:
            db.session.add_all(nuevas)
            db.session.commit()
            flash(f"{len(nuevas)} registros guardados. Neto: {formato_pesos(sum(v.neto for v in nuevas))}.", "success")
        return redirect(url_for("ventas.dia", fecha=fecha))

    registros = (Venta.query.options(joinedload(Venta.vendedora))
                 .filter_by(fecha=fecha_venta).order_by(Venta.id).all())
    return render_template(
        "ventas/dia.html",
        fecha_venta=fecha_venta,
        registros=registros,
        total=sum(r.neto for r in registros),
        vendedoras=vendedoras,
        canales=CANALES,
        medios=MEDIOS_VENTA,
        contactos=MEDIOS_CONTACTO,
        anterior=(fecha_venta - timedelta(days=1)).isoformat(),
        siguiente=(fecha_venta + timedelta(days=1)).isoformat(),
    )


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    venta = db.get_or_404(Venta, id)
    fecha = venta.fecha.isoformat()
    db.session.delete(venta)
    db.session.commit()
    flash("Registro eliminado.", "info")
    return redirect(url_for("ventas.dia", fecha=fecha))


@bp.route("/vendedoras", methods=["GET", "POST"])
def vendedoras():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre es obligatorio.", "danger")
        else:
            db.session.add(Vendedora(nombre=nombre, fecha_ingreso=a_fecha(request.form.get("fecha_ingreso"))))
            try:
                db.session.commit()
                flash(f"Vendedora {nombre} creada.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("Ya existe una vendedora con ese nombre.", "danger")
        return redirect(url_for("ventas.vendedoras"))

    lista = Vendedora.query.order_by(Vendedora.activa.desc(), Vendedora.nombre).all()
    return render_template("ventas/vendedoras.html", vendedoras=lista)


@bp.route("/vendedoras/<int:id>/estado", methods=["POST"])
def cambiar_estado(id):
    vendedora = db.get_or_404(Vendedora, id)
    vendedora.activa = not vendedora.activa
    db.session.commit()
    flash(f"{vendedora.nombre} ahora está {'activa' if vendedora.activa else 'inactiva'}.", "info")
    return redirect(url_for("ventas.vendedoras"))