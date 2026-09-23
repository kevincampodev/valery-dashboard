from flask import (render_template, request, redirect, url_for, flash,
                   send_from_directory, current_app)
from sqlalchemy.exc import IntegrityError

from . import bp
from ...extensions import db
from ...models import Proveedor, Factura, Documento
from ...services.archivos import guardar_archivo
from ...utils import a_pesos, a_fecha


@bp.route("/")
def index():
    proveedor_id = request.args.get("proveedor", type=int)
    estado = request.args.get("estado", "")

    consulta = Factura.query
    if proveedor_id:
        consulta = consulta.filter_by(proveedor_id=proveedor_id)
    facturas = sorted(consulta.all(), key=lambda f: f.fecha_limite)

    if estado:
        facturas = [f for f in facturas if f.estado == estado]

    return render_template(
        "deudas/index.html",
        facturas=facturas,
        proveedores=Proveedor.query.order_by(Proveedor.nombre).all(),
        total_saldo=sum(f.saldo for f in facturas),
        proveedor_id=proveedor_id,
        estado=estado,
    )


@bp.route("/proveedores", methods=["GET", "POST"])
def proveedores():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return redirect(url_for("deudas.proveedores"))

        proveedor = Proveedor(
            nombre=nombre,
            nit=request.form.get("nit", "").strip() or None,
            telefono=request.form.get("telefono", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            dias_credito=request.form.get("dias_credito", type=int) or 0,
        )
        db.session.add(proveedor)
        try:
            db.session.commit()
            flash(f"Proveedor {nombre} creado.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un proveedor con ese nombre o NIT.", "danger")
        return redirect(url_for("deudas.proveedores"))

    return render_template("deudas/proveedores.html",
                           proveedores=Proveedor.query.order_by(Proveedor.nombre).all())


@bp.route("/nueva", methods=["GET", "POST"])
@bp.route("/<int:id>/editar", methods=["GET", "POST"])
def formulario(id=None):
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    factura = db.get_or_404(Factura, id) if id else Factura()

    if request.method == "POST":
        f = request.form
        factura.proveedor_id = f.get("proveedor_id", type=int)
        factura.numero = f.get("numero", "").strip().upper()
        factura.fecha_emision = a_fecha(f.get("fecha_emision"))
        factura.fecha_vencimiento = a_fecha(f.get("fecha_vencimiento"))
        factura.fecha_pactada = a_fecha(f.get("fecha_pactada"))
        factura.subtotal = a_pesos(f.get("subtotal"))
        factura.iva = a_pesos(f.get("iva"))
        factura.total = a_pesos(f.get("total"))
        factura.etiqueta = f.get("etiqueta", "").strip() or None
        factura.cufe = f.get("cufe", "").strip() or None
        factura.pagada_contado = "pagada_contado" in f
        factura.notas = f.get("notas", "").strip() or None

        errores = []
        if not factura.proveedor_id:
            errores.append("Selecciona un proveedor.")
        if not factura.numero:
            errores.append("El número de factura es obligatorio.")
        if not factura.fecha_emision or not factura.fecha_vencimiento:
            errores.append("Las fechas de emisión y vencimiento son obligatorias.")
        if factura.total <= 0:
            errores.append("El total debe ser mayor a cero.")

        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("deudas/form.html", factura=factura, proveedores=proveedores)

        if not id:
            db.session.add(factura)
        try:
            db.session.flush()  # valida duplicados ANTES de guardar archivos
        except IntegrityError:
            db.session.rollback()
            flash("Esa factura ya existe para ese proveedor (o el CUFE ya está registrado).", "danger")
            return render_template("deudas/form.html", factura=factura, proveedores=proveedores)

        for archivo in request.files.getlist("archivos"):
            if archivo and archivo.filename:
                try:
                    ruta, tipo = guardar_archivo(archivo, "facturas")
                except ValueError as e:
                    flash(str(e), "warning")
                    continue
                factura.documentos.append(
                    Documento(nombre_original=archivo.filename, ruta=ruta, tipo=tipo))

        db.session.commit()
        flash(f"Factura {factura.numero} guardada.", "success")
        return redirect(url_for("deudas.detalle", id=factura.id))

    return render_template("deudas/form.html", factura=factura, proveedores=proveedores)


@bp.route("/<int:id>")
def detalle(id):
    return render_template("deudas/detalle.html", factura=db.get_or_404(Factura, id))


@bp.route("/documento/<int:id>")
def documento(id):
    doc = db.get_or_404(Documento, id)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], doc.ruta,
                               download_name=doc.nombre_original)