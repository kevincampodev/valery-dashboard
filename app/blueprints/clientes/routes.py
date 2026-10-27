"""Base de datos de clientes minoristas (los mayoristas tienen su propio módulo)."""
import re
from datetime import date, datetime

from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import Cliente, Venta, NETO_SQL
from ...services.clientes import normalizar_telefono, formato_telefono
from ...utils import rango_mes

ORDENES = {"reciente": "Última compra", "total": "Más compras ($)", "nombre": "Nombre"}


def _estadisticas():
    """Por cliente: compras, total, primera y última compra, y la red por la que llegó (su primera compra)."""
    datos = {}
    for cliente_id, fecha, valor, contacto in (
            db.session.query(Venta.cliente_id, Venta.fecha, NETO_SQL, Venta.medio_contacto)
            .filter(Venta.cliente_id.isnot(None)).order_by(Venta.fecha, Venta.id)):
        d = datos.setdefault(cliente_id, {"compras": 0, "total": 0, "primera": fecha, "ultima": fecha,
                                          "llego_por": contacto})
        d["compras"] += 1
        d["total"] += valor
        d["ultima"] = fecha
    return datos


@bp.route("/")
def index():
    texto = request.args.get("q", "").strip()
    autoriza = request.args.get("autoriza", "")
    llego_por = request.args.get("red", "")
    orden = request.args.get("orden", "reciente")

    consulta = Cliente.query.filter_by(es_mayorista=False)
    if texto:
        digitos = re.sub(r"\D", "", texto)
        condiciones = [Cliente.nombre.ilike(f"%{texto}%")]
        if len(digitos) >= 4:
            condiciones.append(Cliente.telefono.like(f"%{digitos}%"))
        consulta = consulta.filter(or_(*condiciones))
    if autoriza in ("si", "no"):
        consulta = consulta.filter(Cliente.autoriza_datos == (autoriza == "si"))
    clientes = consulta.all()

    estadisticas = _estadisticas()
    vacio = {"compras": 0, "total": 0, "primera": None, "ultima": None, "llego_por": None}
    filas = [(c, estadisticas.get(c.id, vacio)) for c in clientes]
    if llego_por:
        filas = [(c, e) for c, e in filas if (e["llego_por"] or "Sin dato") == llego_por]
    if orden == "total":
        filas.sort(key=lambda f: -f[1]["total"])
    elif orden == "nombre":
        filas.sort(key=lambda f: f[0].nombre.lower())
    else:
        filas.sort(key=lambda f: f[1]["ultima"] or date.min, reverse=True)

    inicio, fin = rango_mes(date.today().replace(day=1))
    todos = [(c, estadisticas.get(c.id, vacio)) for c in Cliente.query.filter_by(es_mayorista=False)]
    resumen = {
        "total": len(todos),
        "nuevos_mes": sum(1 for _, e in todos if e["primera"] and inicio <= e["primera"] <= fin),
        "repiten": sum(1 for _, e in todos if e["compras"] >= 2),
        "autorizan": sum(1 for c, _ in todos if c.autoriza_datos),
    }
    redes = sorted({e["llego_por"] or "Sin dato" for _, e in todos})
    return render_template("clientes/index.html", filas=filas, resumen=resumen, redes=redes, ordenes=ORDENES,
                           filtros={"q": texto, "autoriza": autoriza, "red": llego_por, "orden": orden},
                           formato_telefono=formato_telefono)


@bp.route("/<int:id>")
def detalle(id):
    cliente = db.get_or_404(Cliente, id)
    compras = (Venta.query.options(joinedload(Venta.vendedora), selectinload(Venta.lineas))
               .filter_by(cliente_id=cliente.id)
               .order_by(Venta.fecha.desc(), Venta.numero_factura.desc(), Venta.id.desc()).all())
    return render_template("clientes/detalle.html", cliente=cliente, compras=compras,
                           total=sum(v.neto for v in compras), formato_telefono=formato_telefono)


@bp.route("/<int:id>/editar", methods=["POST"])
def editar(id):
    cliente = db.get_or_404(Cliente, id)
    f = request.form
    nombre = " ".join(f.get("nombre", "").split())[:120]
    if not nombre:
        flash("El cliente necesita un nombre.", "danger")
        return redirect(url_for("clientes.detalle", id=id))

    telefono_texto = f.get("telefono", "").strip()
    telefono = normalizar_telefono(telefono_texto)
    if telefono_texto and not telefono:
        flash("El celular no es válido (deben ser 10 dígitos).", "danger")
        return redirect(url_for("clientes.detalle", id=id))
    if telefono and Cliente.query.filter(Cliente.telefono == telefono, Cliente.id != cliente.id).first():
        flash("Ese celular ya lo tiene otro cliente.", "danger")
        return redirect(url_for("clientes.detalle", id=id))

    documento = f.get("documento", "").strip()[:20] or None
    if documento and Cliente.query.filter(Cliente.documento == documento, Cliente.id != cliente.id).first():
        flash("Ese documento ya lo tiene otro cliente.", "danger")
        return redirect(url_for("clientes.detalle", id=id))

    autoriza = f.get("autoriza_datos") == "1"
    if autoriza and not cliente.autoriza_datos:
        cliente.fecha_autorizacion = datetime.now()
    if not autoriza:
        cliente.fecha_autorizacion = None
    cliente.autoriza_datos = autoriza
    cliente.nombre = nombre
    cliente.telefono = telefono
    cliente.documento = documento
    cliente.ciudad = f.get("ciudad", "").strip()[:60] or None
    cliente.notas = f.get("notas", "").strip() or None
    db.session.commit()
    flash("Cliente actualizado.", "success")
    return redirect(url_for("clientes.detalle", id=id))
