"""
Ventas por redes sociales (TikTok, Facebook, Instagram) para el equipo de marketing.

Aquí nunca se consultan nombres, teléfonos, vendedoras, precios de compra ni márgenes:
solo fecha, número de factura, valor, red y referencias vendidas.
"""
from datetime import date, timedelta
from io import BytesIO

from flask import render_template, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func

from . import bp
from ...extensions import db
from ...models import Venta, LineaVenta, NETO_SQL
from ...services.marketing import REDES_PAUTA
from ...services.redes import (DIAS_SEMANA, periodo_comparable, resumen_por_red, por_dia_semana,
                               clientes_nuevos)
from ...utils import mes_desde_texto, rango_mes, nombre_mes

TOP_REFERENCIAS = 10
COLORES = {"TikTok": "#111827", "Facebook": "#1877f2", "Instagram": "#d62976"}


def _mes():
    inicio, fin = rango_mes(mes_desde_texto(request.args.get("mes")))
    return inicio, fin


def _navegacion(inicio, fin):
    return {
        "titulo": nombre_mes(inicio),
        "mes": inicio.strftime("%Y-%m"),
        "anterior": (inicio - timedelta(days=1)).strftime("%Y-%m"),
        "siguiente": (fin + timedelta(days=1)).strftime("%Y-%m"),
    }


def _de_redes(desde, hasta):
    return Venta.query.filter(Venta.fecha.between(desde, hasta), Venta.medio_contacto.in_(REDES_PAUTA))


@bp.route("/")
def index():
    hoy = date.today()
    inicio, fin = _mes()
    desde_ant, hasta_ant = periodo_comparable(inicio, fin, hoy)

    columnas = (Venta.fecha, Venta.medio_contacto, NETO_SQL, Venta.cliente_id)
    actuales = _de_redes(inicio, fin).with_entities(*columnas).all()
    anteriores = _de_redes(desde_ant, hasta_ant).with_entities(Venta.medio_contacto, NETO_SQL).all()

    resumen = resumen_por_red([(red, valor) for _, red, valor, _ in actuales], anteriores)
    semana = por_dia_semana([(f, red, valor) for f, red, valor, _ in actuales])

    ids = {c for *_, c in actuales if c}
    primera = dict(db.session.query(Venta.cliente_id, func.min(Venta.fecha))
                   .filter(Venta.cliente_id.in_(ids)).group_by(Venta.cliente_id)) if ids else {}
    clientes = clientes_nuevos([(c, red) for _, red, _, c in actuales], primera, inicio)

    referencias = (db.session.query(LineaVenta.referencia, func.max(LineaVenta.descripcion),
                                    func.sum(LineaVenta.cantidad), func.count(func.distinct(Venta.id)))
                   .join(Venta)
                   .filter(Venta.fecha.between(inicio, fin), Venta.medio_contacto.in_(REDES_PAUTA),
                           Venta.es_devolucion.is_(False))
                   .group_by(LineaVenta.referencia)
                   .order_by(func.sum(LineaVenta.cantidad).desc())
                   .limit(TOP_REFERENCIAS).all())

    return render_template(
        "redes/index.html", redes=REDES_PAUTA, colores=COLORES, resumen=resumen, clientes=clientes, referencias=referencias,
        grafica={"dias": DIAS_SEMANA, "series": semana},
        comparado=(desde_ant, hasta_ant), **_navegacion(inicio, fin),
    )


def _facturas(inicio, fin, red):
    consulta = _de_redes(inicio, fin)
    if red in REDES_PAUTA:
        consulta = consulta.filter(Venta.medio_contacto == red)
    filas = (consulta.with_entities(Venta.fecha, Venta.numero_factura, NETO_SQL, Venta.medio_contacto)
             .order_by(Venta.fecha, Venta.numero_factura, Venta.id).all())
    return [{"fecha": f, "numero": n, "valor": v, "red": r} for f, n, v, r in filas]


@bp.route("/facturas")
def facturas():
    inicio, fin = _mes()
    red = request.args.get("red", "")
    filas = _facturas(inicio, fin, red)
    return render_template("redes/facturas.html", filas=filas, redes=REDES_PAUTA, red=red,
                           total=sum(f["valor"] for f in filas), **_navegacion(inicio, fin))


@bp.route("/facturas/excel")
def descargar():
    inicio, fin = _mes()
    red = request.args.get("red", "")
    wb = Workbook()
    ws = wb.active
    ws.title = "Facturas por redes"
    ws.append(["Fecha", "N.º factura", "Valor", "Red social"])
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for f in _facturas(inicio, fin, red):
        ws.append([f["fecha"], f["numero"], f["valor"], f["red"]])
        ws.cell(ws.max_row, 1).number_format = "DD/MM/YYYY"
        ws.cell(ws.max_row, 3).number_format = "$#,##0"
    for letra, ancho in zip("ABCD", (12, 12, 14, 14)):
        ws.column_dimensions[letra].width = ancho

    archivo = BytesIO()
    wb.save(archivo)
    archivo.seek(0)
    nombre = f"facturas-redes-{inicio:%Y-%m}{'-' + red.lower() if red in REDES_PAUTA else ''}.xlsx"
    return send_file(archivo, as_attachment=True, download_name=nombre,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
