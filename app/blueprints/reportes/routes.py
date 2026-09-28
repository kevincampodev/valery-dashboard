from datetime import date

from flask import render_template, request, send_file

from . import bp
from ...services.reportes import generar_reporte_mensual
from ...utils import mes_desde_texto, rango_mes


@bp.route("/")
def index():
    return render_template("reportes/index.html", mes_actual=date.today().strftime("%Y-%m"))


@bp.route("/mensual")
def mensual():
    inicio, fin = rango_mes(mes_desde_texto(request.args.get("mes")))
    return send_file(
        generar_reporte_mensual(inicio, fin),
        as_attachment=True,
        download_name=f"reporte-{inicio:%Y-%m}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )