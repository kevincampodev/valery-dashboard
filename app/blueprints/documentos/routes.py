import os

from flask import render_template, request, send_from_directory, current_app

from . import bp
from ...extensions import db
from ...models import Documento

FILTROS = {
    "factura": Documento.factura_id.isnot(None),
    "pago": Documento.pago_id.isnot(None),
    "liquidacion": Documento.liquidacion_id.isnot(None),
}


@bp.route("/")
def index():
    tipo = request.args.get("tipo", "")
    texto = request.args.get("q", "").strip()

    consulta = Documento.query
    if tipo in FILTROS:
        consulta = consulta.filter(FILTROS[tipo])
    if texto:
        consulta = consulta.filter(Documento.nombre_original.ilike(f"%{texto}%"))
    documentos = consulta.order_by(Documento.subido_en.desc()).limit(300).all()

    carpeta = current_app.config["UPLOAD_FOLDER"]
    tamanos = {}
    for d in documentos:
        ruta = os.path.join(carpeta, d.ruta)
        tamanos[d.id] = os.path.getsize(ruta) if os.path.exists(ruta) else None

    return render_template("documentos/index.html", documentos=documentos, tamanos=tamanos,
                           tipo=tipo, texto=texto,
                           conteos={k: Documento.query.filter(f).count() for k, f in FILTROS.items()})


@bp.route("/<int:id>")
def ver(id):
    doc = db.get_or_404(Documento, id)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], doc.ruta,
                               download_name=doc.nombre_original)