import io
import zipfile
from xml.etree.ElementTree import ParseError

from datetime import date

from flask import render_template, request, redirect, url_for, flash, send_file
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.datastructures import FileStorage

from . import bp
from ...extensions import db
from ...models import Proveedor, Factura, Documento, Pago, AplicacionPago
from ...services.deudas_vista import (PESTANAS, ESTADOS, fila, en_pestana, filtrar, ordenar, resumen, totales,
                                      por_proveedor, meses_disponibles)
from ...services.archivos import guardar_archivo
from ...services.dian import parsear_xml, extraer_paquetes
from ...services.cartera import cartera_por_edades, RANGOS
from ...utils import a_pesos, a_fecha, nit_base, normalizar


def _filtros():
    """Lee los filtros de la dirección. Así la página, el Excel y los enlaces del Inicio usan las mismas reglas."""
    a = request.args
    estado = a.get("estado", "") if a.get("estado", "") in ESTADOS else ""
    pestana = a.get("ver", "")
    if pestana not in PESTANAS:
        # los enlaces del Inicio llegan con ?estado=...: se abre la pestaña que corresponde
        pestana = {"vencida": "vencidas", "pagada": "pagadas"}.get(estado, "pendientes" if estado else "pendientes")
    mes = a.get("mes", "")
    return {"pestana": pestana, "estado": estado, "proveedor_id": a.get("proveedor", type=int),
            "texto": a.get("q", "").strip()[:60], "mes": mes if len(mes) == 7 else "",
            "vista": "proveedores" if a.get("vista") == "proveedores" else "facturas"}


def _filas():
    hoy = date.today()
    facturas = (Factura.query.options(joinedload(Factura.proveedor),
                                      selectinload(Factura.aplicaciones).joinedload(AplicacionPago.pago)).all())
    return [fila(f, hoy) for f in facturas]


def _aplicar(todas, filtros):
    vista = filtrar(todas, filtros["proveedor_id"], filtros["estado"], filtros["texto"], filtros["mes"])
    return ordenar(en_pestana(vista, filtros["pestana"])), vista


@bp.route("/")
def index():
    filtros = _filtros()
    todas = _filas()
    filas, sin_pestana = _aplicar(todas, filtros)
    inicio_mes = date.today().replace(day=1)
    pagos_mes = Pago.query.filter(Pago.fecha >= inicio_mes).all()

    def url_con(**cambios):
        """La misma página cambiando solo algunos filtros (pestaña, vista, estado...)."""
        args = request.args.to_dict()
        args.update(cambios)
        return url_for("deudas.index", **{k: v for k, v in args.items() if v not in (None, "")})

    return render_template(
        "deudas/index.html",
        url_con=url_con,
        excel=url_for("deudas.excel", **request.args.to_dict()),
        filas=filas,
        f=filtros,
        resumen=resumen(todas),
        abonado_mes=sum(p.valor for p in pagos_mes), n_abonos_mes=len(pagos_mes),
        conteos={p: len(en_pestana(sin_pestana, p)) for p in PESTANAS},
        pestanas=PESTANAS, estados=ESTADOS,
        totales=totales(filas),
        grupos=por_proveedor(filas) if filtros["vista"] == "proveedores" else [],
        proveedores=Proveedor.query.order_by(Proveedor.nombre).all(),
        meses=meses_disponibles(todas),
        hoy=date.today(),
    )


@bp.route("/excel")
def excel():
    """Exactamente lo que se está viendo en pantalla (misma pestaña y filtros)."""
    filtros = _filtros()
    filas, _ = _aplicar(_filas(), filtros)
    wb = Workbook()
    ws = wb.active
    ws.title = "Deudas"
    ws.append(["Proveedor", "Factura", "Etiqueta", "Emisión", "Fecha límite", "Fecha original", "Total",
               "Abonado", "Saldo", "Estado", "Días", "Pagada el"])
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for x in filas:
        ws.append([x["proveedor"], x["numero"], x["etiqueta"] or "", x["emision"], x["limite"], x["original"],
                   x["total"], x["abonado"], x["saldo"], x["estado"].capitalize(),
                   x["dias"] if x["saldo"] else None, x["fecha_pago"]])
        for col in (4, 5, 6, 12):
            ws.cell(ws.max_row, col).number_format = "DD/MM/YYYY"
        for col in (7, 8, 9):
            ws.cell(ws.max_row, col).number_format = "$#,##0"
    t = totales(filas)
    ws.append([])
    ws.append(["Totales", f"{t['numero']} facturas", "", None, None, None, t["total"], t["abonado"], t["saldo"]])
    for col in (7, 8, 9):
        ws.cell(ws.max_row, col).number_format = "$#,##0"
    for celda in ws[ws.max_row]:
        celda.font = Font(bold=True)
    for letra, ancho in zip("ABCDEFGHIJKL", (26, 16, 20, 12, 13, 14, 15, 15, 15, 12, 7, 12)):
        ws.column_dimensions[letra].width = ancho
    ws.freeze_panes = "A2"

    archivo = io.BytesIO()
    wb.save(archivo)
    archivo.seek(0)
    return send_file(archivo, as_attachment=True, download_name=f"deudas-{filtros['pestana']}-{date.today():%Y-%m-%d}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


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


@bp.route("/importar", methods=["GET", "POST"])
def importar():
    resultados = []
    if request.method == "POST":
        etiqueta = request.form.get("etiqueta", "").strip() or None
        paquetes = []
        for archivo in request.files.getlist("archivos"):
            if not archivo or not archivo.filename:
                continue
            try:
                paquetes += extraer_paquetes(archivo.filename, archivo.read())
            except zipfile.BadZipFile:
                resultados.append({"estado": "error", "origen": archivo.filename,
                                   "mensaje": "El ZIP está dañado", "datos": None, "factura": None})

        for paquete in paquetes:
            resultados.append(_importar_paquete(paquete, etiqueta))

        if not resultados:
            flash("No se encontró ningún XML de factura en lo que subiste.", "warning")

    return render_template("deudas/importar.html", resultados=resultados)


def _buscar_proveedor(nit, nombre):
    for p in Proveedor.query.all():
        if nit and nit_base(p.nit) == nit_base(nit):
            return p
        if nombre and normalizar(p.nombre) == normalizar(nombre):
            return p
    return None


def _importar_paquete(paquete, etiqueta):
    xml_nombre, xml_bytes = paquete["xml"]
    r = {"origen": paquete["origen"], "estado": "error", "mensaje": "", "datos": None, "factura": None}

    try:
        datos = parsear_xml(xml_bytes)
    except (ValueError, TypeError, ParseError) as e:
        r["mensaje"] = f"No se pudo leer {xml_nombre}: {e}"
        return r
    r["datos"] = datos

    if Factura.query.filter_by(cufe=datos["cufe"]).first():
        r.update(estado="duplicada", mensaje="Ya estaba registrada (mismo CUFE)")
        return r

    proveedor = _buscar_proveedor(datos["proveedor_nit"], datos["proveedor_nombre"])
    proveedor_nuevo = proveedor is None
    if proveedor_nuevo:
        proveedor = Proveedor(nombre=datos["proveedor_nombre"], nit=datos["proveedor_nit"])
        db.session.add(proveedor)
    elif Factura.query.filter_by(proveedor_id=proveedor.id, numero=datos["numero"]).first():
        r.update(estado="duplicada", mensaje="Ya se había cargado a mano (mismo número)")
        return r

    factura = Factura(
        proveedor=proveedor,
        numero=datos["numero"],
        fecha_emision=datos["fecha_emision"],
        fecha_vencimiento=datos["fecha_vencimiento"],
        subtotal=datos["subtotal"],
        iva=datos["iva"],
        total=datos["total"],
        cufe=datos["cufe"],
        etiqueta=etiqueta,
        notas=f"Importada desde XML DIAN. Forma de pago: {datos['forma_pago']}.",
    )
    db.session.add(factura)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        r["mensaje"] = "Conflicto al guardar (posible duplicado)"
        return r

    for nombre, contenido in [paquete["xml"]] + paquete["pdfs"]:
        archivo = FileStorage(stream=io.BytesIO(contenido), filename=nombre)
        ruta, tipo = guardar_archivo(archivo, "facturas")
        factura.documentos.append(Documento(nombre_original=nombre, ruta=ruta, tipo=tipo))

    db.session.commit()
    r.update(estado="importada", factura=factura,
             mensaje="Proveedor creado automáticamente" if proveedor_nuevo else "")
    return r


@bp.route("/cartera")
def cartera():
    filas, totales = cartera_por_edades(Factura.query.all())
    return render_template("deudas/cartera.html", filas=filas, totales=totales, rangos=RANGOS)