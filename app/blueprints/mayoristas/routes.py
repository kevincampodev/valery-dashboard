from datetime import date
from types import SimpleNamespace

from flask import render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import (Cliente, LineaVenta, Venta, Vendedora, Parametro, MEDIOS_VENTA, MEDIOS_CONTACTO, NETO_SQL)
from ...services.mayoristas import (normalizar_referencia, leer_lineas, total_lineas, historial_precios,
                                    UMBRAL_MAYORISTA_DEFECTO)
from ...utils import a_fecha, a_pesos, formato_pesos, rango_mes


def umbral_mayorista():
    return Parametro.obtener_int("umbral_mayorista", UMBRAL_MAYORISTA_DEFECTO)


@bp.route("/")
def index():
    texto = request.args.get("q", "").strip()
    consulta = Cliente.query
    if texto:
        patron = f"%{texto}%"
        consulta = consulta.filter(or_(Cliente.nombre.ilike(patron), Cliente.documento.ilike(patron),
                                       Cliente.telefono.ilike(patron), Cliente.ciudad.ilike(patron)))
    clientes = consulta.order_by(Cliente.activo.desc(), Cliente.nombre).all()

    estadisticas = {
        cliente_id: {"total": total or 0, "compras": compras, "ultima": ultima}
        for cliente_id, total, compras, ultima in db.session.query(
            Venta.cliente_id, func.sum(NETO_SQL), func.count(Venta.id), func.max(Venta.fecha)
        ).filter(Venta.cliente_id.isnot(None)).group_by(Venta.cliente_id).all()
    }

    inicio, fin = rango_mes(date.today().replace(day=1))
    del_mes = Venta.query.filter(Venta.canal == "Mayorista", Venta.fecha.between(inicio, fin)).all()
    sin_cliente = db.session.query(func.count(Venta.id), func.sum(NETO_SQL)).filter(
        Venta.canal == "Mayorista", Venta.cliente_id.is_(None)).one()

    return render_template(
        "mayoristas/index.html", clientes=clientes, estadisticas=estadisticas, texto=texto,
        ventas_mes=sum(v.neto for v in del_mes), compras_mes=len(del_mes),
        sin_cliente={"cantidad": sin_cliente[0], "total": sin_cliente[1] or 0},
        umbral=umbral_mayorista(),
    )


@bp.route("/umbral", methods=["POST"])
def guardar_umbral():
    valor = a_pesos(request.form.get("umbral"))
    if valor <= 0:
        flash("El umbral debe ser mayor a cero.", "danger")
    else:
        Parametro.guardar("umbral_mayorista", valor)
        db.session.commit()
        flash(f"Desde ahora, una venta mayorista debe pasar de {formato_pesos(valor)}.", "success")
    return redirect(url_for("mayoristas.index"))


@bp.route("/clientes", methods=["POST"])
def crear_cliente():
    f = request.form
    nombre = f.get("nombre", "").strip()
    if not nombre:
        flash("El cliente necesita un nombre.", "danger")
        return redirect(url_for("mayoristas.index"))
    cliente = Cliente(nombre=nombre, documento=f.get("documento", "").strip() or None,
                      telefono=f.get("telefono", "").strip() or None, ciudad=f.get("ciudad", "").strip() or None)
    db.session.add(cliente)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Ya existe un cliente con ese documento.", "danger")
        return redirect(url_for("mayoristas.index"))
    flash(f"Cliente {nombre} creado.", "success")
    return redirect(url_for("mayoristas.cliente", id=cliente.id))


@bp.route("/cliente/<int:id>")
def cliente(id):
    cliente = db.get_or_404(Cliente, id)
    ventas = (Venta.query.options(selectinload(Venta.lineas), joinedload(Venta.vendedora))
              .filter_by(cliente_id=id).order_by(Venta.fecha.desc(), Venta.id.desc()).all())
    registros = [SimpleNamespace(referencia=l.referencia, cantidad=l.cantidad, precio_unitario=l.precio_unitario,
                                 fecha=v.fecha, cliente=cliente.nombre)
                 for v in ventas for l in v.lineas]
    return render_template("mayoristas/cliente.html", cliente=cliente, ventas=ventas,
                           precios=historial_precios(registros), total=sum(v.neto for v in ventas))


@bp.route("/cliente/<int:id>/editar", methods=["POST"])
def editar_cliente(id):
    cliente = db.get_or_404(Cliente, id)
    f = request.form
    if not f.get("nombre", "").strip():
        flash("El nombre no puede quedar vacío.", "danger")
        return redirect(url_for("mayoristas.cliente", id=id))
    cliente.nombre = f.get("nombre").strip()
    cliente.documento = f.get("documento", "").strip() or None
    cliente.telefono = f.get("telefono", "").strip() or None
    cliente.ciudad = f.get("ciudad", "").strip() or None
    cliente.notas = f.get("notas", "").strip() or None
    cliente.activo = "activo" in f
    try:
        db.session.commit()
        flash("Datos del cliente actualizados.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Ya existe otro cliente con ese documento.", "danger")
    return redirect(url_for("mayoristas.cliente", id=id))


@bp.route("/venta/nueva", methods=["GET", "POST"])
def nueva_venta():
    vendedores = Vendedora.query.filter_by(activa=True, vende_mayorista=True).order_by(Vendedora.nombre).all()
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()

    if request.method == "POST":
        f = request.form
        lineas, errores = leer_lineas(f.getlist("referencia"), f.getlist("cantidad"), f.getlist("precio"))
        if not lineas and not errores:
            errores.append("Agrega al menos una prenda.")
        umbral = umbral_mayorista()
        if lineas and total_lineas(lineas) <= umbral:
            errores.append(f"El total es {formato_pesos(total_lineas(lineas))}: las ventas de hasta "
                           f"{formato_pesos(umbral)} son minoristas. Regístrala en Ventas diarias.")

        vendedora_id = f.get("vendedora_id", type=int)
        if vendedora_id not in {v.id for v in vendedores}:
            errores.append("Selecciona quién hizo la venta.")
        if f.get("medio_pago") not in MEDIOS_VENTA:
            errores.append("Selecciona el medio de pago.")
        if f.get("medio_contacto") not in MEDIOS_CONTACTO:
            errores.append("Selecciona cómo llegó el cliente.")

        cliente_id = f.get("cliente_id", type=int)
        cliente = db.session.get(Cliente, cliente_id) if cliente_id else None
        nuevo_nombre = f.get("nuevo_nombre", "").strip()
        if not cliente and not nuevo_nombre:
            errores.append("Selecciona el cliente o escribe el nombre de uno nuevo.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template(
                "mayoristas/venta.html", vendedores=vendedores, clientes=clientes, medios=MEDIOS_VENTA,
                contactos=MEDIOS_CONTACTO, form=f, hoy=date.today(),
                lineas_form=list(zip(f.getlist("referencia"), f.getlist("cantidad"), f.getlist("precio"))))

        if not cliente:
            cliente = Cliente(nombre=nuevo_nombre, telefono=f.get("nuevo_telefono", "").strip() or None)
            db.session.add(cliente)

        venta = Venta(
            fecha=a_fecha(f.get("fecha")) or date.today(), canal="Mayorista", vendedora_id=vendedora_id,
            cliente=cliente, medio_pago=f.get("medio_pago"), medio_contacto=f.get("medio_contacto"),
            valor=total_lineas(lineas), prendas=sum(l["cantidad"] for l in lineas), origen="manual",
        )
        venta.lineas.extend(LineaVenta(**linea) for linea in lineas)
        db.session.add(venta)
        db.session.commit()

        flash(f"Venta mayorista de {formato_pesos(venta.valor)} a {cliente.nombre} registrada.", "success")
        return redirect(url_for("mayoristas.cliente", id=cliente.id))

    return render_template("mayoristas/venta.html", vendedores=vendedores, clientes=clientes,
                           medios=MEDIOS_VENTA, contactos=MEDIOS_CONTACTO, form={}, lineas_form=[],
                           hoy=date.today(), cliente_inicial=request.args.get("cliente", type=int))


@bp.route("/precios")
def precios():
    texto = normalizar_referencia(request.args.get("ref"))
    consulta = (db.session.query(LineaVenta.referencia, LineaVenta.cantidad, LineaVenta.precio_unitario,
                                 Venta.fecha, Cliente.nombre.label("cliente"))
                .join(Venta, LineaVenta.venta_id == Venta.id)
                .outerjoin(Cliente, Venta.cliente_id == Cliente.id))
    if texto:
        consulta = consulta.filter(LineaVenta.referencia.like(f"%{texto}%"))
    return render_template("mayoristas/precios.html", precios=historial_precios(consulta.all()), texto=texto)


@bp.route("/precio")
def precio():
    """JSON con el último precio de una referencia, para sugerirlo en el formulario."""
    referencia = normalizar_referencia(request.args.get("ref"))
    if not referencia:
        return jsonify({})
    base = (db.session.query(LineaVenta.precio_unitario, Venta.fecha)
            .join(Venta, LineaVenta.venta_id == Venta.id)
            .filter(LineaVenta.referencia == referencia)
            .order_by(Venta.fecha.desc(), LineaVenta.id.desc()))
    cliente_id = request.args.get("cliente", type=int)

    def formato(fila):
        return {"precio": fila.precio_unitario, "fecha": fila.fecha.strftime("%d/%m/%Y")} if fila else None

    return jsonify({
        "referencia": referencia,
        "cliente": formato(base.filter(Venta.cliente_id == cliente_id).first()) if cliente_id else None,
        "general": formato(base.first()),
    })