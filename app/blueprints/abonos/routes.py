from datetime import date

from flask import render_template, request, redirect, url_for, flash

from . import bp
from ...extensions import db
from ...models import Proveedor, Pago, AplicacionPago, Documento, MEDIOS_PAGO
from ...services.abonos import distribuir_fifo
from ...services.archivos import guardar_archivo, borrar_archivo
from ...utils import a_pesos, a_fecha, formato_pesos


@bp.route("/")
def index():
    proveedor_id = request.args.get("proveedor", type=int)
    consulta = Pago.query
    if proveedor_id:
        consulta = consulta.filter_by(proveedor_id=proveedor_id)
    pagos = consulta.order_by(Pago.fecha.desc(), Pago.id.desc()).all()

    return render_template(
        "abonos/index.html",
        pagos=pagos,
        proveedores=Proveedor.query.order_by(Proveedor.nombre).all(),
        proveedor_id=proveedor_id,
        total=sum(p.valor for p in pagos),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    proveedor_id = request.values.get("proveedor", type=int)
    proveedor = db.session.get(Proveedor, proveedor_id) if proveedor_id else None
    pendientes = []
    if proveedor:
        pendientes = sorted((f for f in proveedor.facturas if f.saldo > 0),
                            key=lambda f: f.fecha_limite)

    if request.method == "POST" and proveedor:
        form = request.form
        valor = a_pesos(form.get("valor"))

        manual = {f.id: a_pesos(form.get(f"aplicar_{f.id}")) for f in pendientes}
        manual = {fid: monto for fid, monto in manual.items() if monto > 0}
        if manual:
            plan = [(f, manual[f.id]) for f in pendientes if f.id in manual]
        else:
            plan, _ = distribuir_fifo(pendientes, valor)

        errores = []
        if valor <= 0:
            errores.append("El valor del abono debe ser mayor a cero.")
        if form.get("medio") not in MEDIOS_PAGO:
            errores.append("Selecciona un medio de pago.")
        for factura, monto in plan:
            if monto > factura.saldo:
                errores.append(f"A la factura {factura.numero} solo le quedan "
                               f"{formato_pesos(factura.saldo)} de saldo.")
        if sum(m for _, m in plan) > valor:
            errores.append("Lo repartido entre facturas supera el valor del abono.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("abonos/form.html", proveedores=proveedores, proveedor=proveedor,
                                   pendientes=pendientes, medios=MEDIOS_PAGO, form=form, hoy=date.today())

        pago = Pago(
            proveedor=proveedor,
            fecha=a_fecha(form.get("fecha")) or date.today(),
            valor=valor,
            medio=form.get("medio"),
            referencia=form.get("referencia", "").strip() or None,
            notas=form.get("notas", "").strip() or None,
        )
        for factura, monto in plan:
            pago.aplicaciones.append(AplicacionPago(factura=factura, valor=monto))
        db.session.add(pago)
        db.session.flush()

        for archivo in request.files.getlist("comprobantes"):
            if archivo and archivo.filename:
                try:
                    ruta, tipo = guardar_archivo(archivo, "pagos")
                except ValueError as e:
                    flash(str(e), "warning")
                    continue
                pago.documentos.append(Documento(nombre_original=archivo.filename, ruta=ruta, tipo=tipo))

        db.session.commit()

        mensaje = f"Abono de {formato_pesos(valor)} a {proveedor.nombre} registrado."
        if pago.sin_aplicar:
            mensaje += f" Quedaron {formato_pesos(pago.sin_aplicar)} sin aplicar (saldo a favor)."
        flash(mensaje, "success")
        return redirect(url_for("abonos.index", proveedor=proveedor.id))

    return render_template("abonos/form.html", proveedores=proveedores, proveedor=proveedor,
                           pendientes=pendientes, medios=MEDIOS_PAGO, form=request.form, hoy=date.today())


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    pago = db.get_or_404(Pago, id)
    rutas = [d.ruta for d in pago.documentos]
    proveedor_id = pago.proveedor_id

    db.session.delete(pago)
    db.session.commit()
    for ruta in rutas:
        borrar_archivo(ruta)

    flash("Abono eliminado. Los saldos de las facturas se recalcularon.", "info")
    return redirect(url_for("abonos.index", proveedor=proveedor_id))