from datetime import date, timedelta

from flask import render_template, request, redirect, url_for, flash, abort
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import Venta, Vendedora, Parametro, LineaVenta, CANALES, MEDIOS_VENTA, MEDIOS_CONTACTO
from ...services.mayoristas import es_mayorista, total_lineas, UMBRAL_MAYORISTA_DEFECTO
from ...services.detalle_venta import leer_detalle

TALLAS_BASE = ["XS", "S", "M", "L", "XL", "XXL", "ÚNICA"]
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
    ids_mayoristas = {v.id for v in vendedoras if v.vende_mayorista}
    umbral = Parametro.obtener_int("umbral_mayorista", UMBRAL_MAYORISTA_DEFECTO)

    if request.method == "POST":
        f = request.form
        filas = zip(f.getlist("canal"), f.getlist("vendedora_id"), f.getlist("medio_pago"),
                    f.getlist("tipo"), f.getlist("valor"), f.getlist("prendas"), f.getlist("medio_contacto"),
                    f.getlist("detalle"))

        nuevas, errores = [], []
        for n, (canal, vendedora_id, medio, tipo, valor, prendas, contacto, detalle) in enumerate(filas, start=1):
            cantidad_prendas = int(prendas) if prendas.isdigit() else 0
            lineas, error_detalle = leer_detalle(detalle, cantidad_prendas)
            if error_detalle:
                errores.append(f"Fila {n}: {error_detalle}")
                continue
            valor = total_lineas(lineas) if lineas else a_pesos(valor)
            if valor <= 0:
                continue  # fila vacía: se ignora
            vendedora_id = int(vendedora_id) if vendedora_id else None
            if contacto not in MEDIOS_CONTACTO:
                errores.append(f"Fila {n}: falta el medio de contacto.")
                continue
            if tipo != "devolucion" and es_mayorista(vendedora_id in ids_mayoristas, valor, umbral):
                errores.append(f"Fila {n}: venta de {formato_pesos(valor)} hecha por quien vende al por mayor. "
                               f"Es mayorista: regístrala en Mayoristas → Nueva venta.")
                continue
            if canal != "Minorista" or medio not in MEDIOS_VENTA or (vendedora_id and vendedora_id not in ids_validos):
                errores.append(f"Fila {n}: datos inválidos.")
                continue
            venta = Venta(
                fecha=fecha_venta, canal=canal, vendedora_id=vendedora_id, medio_pago=medio,
                valor=valor, prendas=int(prendas) if prendas.isdigit() else None, medio_contacto=contacto,
                es_devolucion=(tipo == "devolucion"),
            )
            venta.lineas.extend(LineaVenta(**linea) for linea in lineas)
            nuevas.append(venta)

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

    registros = (Venta.query.options(joinedload(Venta.vendedora), selectinload(Venta.lineas))
                 .filter_by(fecha=fecha_venta).order_by(Venta.id).all())

    tallas_usadas = [t for (t,) in db.session.query(LineaVenta.talla)
                     .filter(LineaVenta.talla.isnot(None)).distinct()]
    sugerencias = {
        "referencias": [r for (r,) in db.session.query(LineaVenta.referencia)
                        .distinct().order_by(LineaVenta.referencia).limit(500)],
        "colores": [c for (c,) in db.session.query(LineaVenta.color)
                    .filter(LineaVenta.color.isnot(None)).distinct().order_by(LineaVenta.color)],
        "tallas": TALLAS_BASE + sorted(t for t in tallas_usadas if t not in TALLAS_BASE),
    }
    return render_template(
        "ventas/dia.html",
        fecha_venta=fecha_venta,
        registros=registros,
        total=sum(r.neto for r in registros),
        vendedoras=vendedoras,
        canales=["Minorista"],
        medios=MEDIOS_VENTA,
        contactos=MEDIOS_CONTACTO,
        umbral=umbral,
        sugerencias=sugerencias,
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


@bp.route("/vendedoras/<int:id>/mayorista", methods=["POST"])
def cambiar_mayorista(id):
    vendedora = db.get_or_404(Vendedora, id)
    vendedora.vende_mayorista = not vendedora.vende_mayorista
    db.session.commit()
    estado = "ahora puede" if vendedora.vende_mayorista else "ya no puede"
    flash(f"{vendedora.nombre} {estado} registrar ventas mayoristas.", "info")
    return redirect(url_for("ventas.vendedoras"))