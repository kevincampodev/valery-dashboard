from flask import render_template, request, redirect, url_for, flash, send_from_directory, current_app, abort

from . import bp
from datetime import datetime, timedelta

from ...models import Bitacora, EventoAcceso
from ...services.backups import crear_backup, listar_backups

NOMBRES_TABLAS = {
    "facturas": "Factura", "proveedores": "Proveedor", "pagos": "Abono", "aplicaciones_pago": "Aplicación de abono",
    "ventas": "Venta", "vendedoras": "Vendedora", "liquidaciones": "Liquidación", "metas": "Meta",
    "tramos_incentivo": "Tramo de incentivo", "objetivos": "Objetivo", "documentos": "Documento",
    "cuentas_dinero": "Cuenta de dinero", "gastos_recurrentes": "Gasto fijo", "ajustes_temporada": "Factor de temporada",
    "inversiones_publicidad": "Pauta publicitaria", "parametros": "Parámetro",
    "clientes": "Cliente", "lineas_venta": "Línea de venta", "usuarios": "Usuario",
}


@bp.route("/")
def index():
    carpeta = current_app.config["BACKUP_DIR"]
    return render_template("sistema/index.html", backups=listar_backups(carpeta), carpeta=carpeta,
                           ultimos_cambios=Bitacora.query.order_by(Bitacora.id.desc()).limit(10).all(),
                           nombres=NOMBRES_TABLAS)


@bp.route("/backup", methods=["POST"])
def backup_manual():
    destino = crear_backup(current_app.config["DB_PATH"], current_app.config["BACKUP_DIR"])
    flash(f"Backup creado: {destino}", "success")
    return redirect(url_for("sistema.index"))


@bp.route("/backup/<nombre>")
def descargar_backup(nombre):
    carpeta = current_app.config["BACKUP_DIR"]
    if nombre not in {b["nombre"] for b in listar_backups(carpeta)}:
        abort(404)
    return send_from_directory(carpeta, nombre, as_attachment=True)


@bp.route("/bitacora")
def bitacora():
    tabla = request.args.get("tabla", "")
    accion = request.args.get("accion", "")
    consulta = Bitacora.query
    if tabla:
        consulta = consulta.filter_by(tabla=tabla)
    if accion:
        consulta = consulta.filter_by(accion=accion)
    return render_template("sistema/bitacora.html",
                           registros=consulta.order_by(Bitacora.id.desc()).limit(300).all(),
                           nombres=NOMBRES_TABLAS, tabla=tabla, accion=accion)


@bp.route("/accesos")
def accesos():
    filtro = request.args.get("filtro", "")
    consulta = EventoAcceso.query
    if filtro == "fallidos":
        consulta = consulta.filter_by(exito=False)
    elif filtro == "exitosos":
        consulta = consulta.filter_by(exito=True)

    hace_24h = datetime.now() - timedelta(hours=24)
    return render_template(
        "sistema/accesos.html",
        eventos=consulta.order_by(EventoAcceso.fecha.desc()).limit(300).all(),
        fallidos_24h=EventoAcceso.query.filter(EventoAcceso.exito.is_(False), EventoAcceso.fecha >= hace_24h).count(),
        filtro=filtro,
    )