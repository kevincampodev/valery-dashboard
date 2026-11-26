from datetime import date, datetime, timedelta

from flask import render_template, url_for, request, jsonify
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import Factura, Pago, Meta, Venta, Cliente, NETO_SQL
from ...models.marketing import InversionPublicidad
from ...services.indicadores import resumen_deudas
from ...services.inicio import saludo, proximos_pagos, deuda_proveedores, clientes_para_recuperar
from ...services.metas import avance_meta
from ...services.marketing import REDES_PAUTA, inversion_del_mes
from ...services.tablero_ventas import DIAS_SEMANA, variacion, indicadores, por_dia, acumulado, proyeccion
from ...utils import rango_mes, nombre_mes

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo("America/Bogota")
except Exception:          # sin base de zonas horarias: se usa la hora del servidor
    ZONA = None

DIAS_SIN_COMPRA = 45
RETORNO_EQUILIBRIO = 2   # con 50% de margen, cada $1 de pauta debe vender al menos $2 para no perder
VACIO = {"minorista": 0, "mayorista": 0, "neto": 0, "numero": 0, "prendas": 0}


def _fecha_corta(dia):
    return f"{DIAS_SEMANA[dia.weekday()].lower()} {dia.strftime('%d/%m')}"


def _plural(n, palabra, sufijo="s"):
    return f"{n} {palabra}{sufijo if n != 1 else ''}"


@bp.route("/")
def index():
    hoy = date.today()
    ahora = datetime.now(ZONA) if ZONA else datetime.now()

    # ---------- Ventas del mes (mismas reglas que el tablero de Ventas) ----------
    inicio, fin = rango_mes(hoy.replace(day=1))
    registros = Venta.query.filter(Venta.fecha.between(inicio, fin)).all()
    dias = por_dia(registros, inicio, fin)
    corte = max((r.fecha for r in registros), default=None)      # último día con ventas cargadas

    fin_ant = inicio - timedelta(days=1)
    inicio_ant = fin_ant.replace(day=1)
    anteriores = Venta.query.filter(Venta.fecha.between(inicio_ant, fin_ant)).all()
    dias_ant = por_dia(anteriores, inicio_ant, fin_ant)
    corte_ant = inicio_ant.replace(day=min(corte.day, fin_ant.day)) if corte else None
    actual = indicadores(registros)
    previo = indicadores([r for r in anteriores if corte_ant and r.fecha <= corte_ant])

    meta = Meta.query.filter_by(periodo=inicio, canal="Total").first()
    avance = avance_meta(actual["neto"], meta.valor, inicio, fin, corte + timedelta(days=1)) if meta and corte else None
    cierre = proyeccion(dias, corte, fin)[1] if corte else None

    # Último día cargado frente al promedio de los días con ventas
    con_ventas = [d["neto"] for f, d in dias.items() if corte and f <= corte and d["neto"]]
    promedio = sum(con_ventas) / len(con_ventas) if con_ventas else 0
    ultimo = dias[corte] if corte else None

    # Últimos 7 días cargados (pueden venir del mes anterior) y mini gráficas de las tarjetas
    todos = {**dias_ant, **dias}
    siete = [corte - timedelta(days=i) for i in range(6, -1, -1)] if corte else []
    grafica = {
        "siete": [{"etiqueta": f"{DIAS_SEMANA[f.weekday()]} {f.day}", "url": url_for("ventas.dia", fecha=f.isoformat()),
                   "festivo": todos.get(f, {}).get("festivo", False), **{k: todos.get(f, VACIO)[k] for k in VACIO}}
                  for f in siete],
        "acumulado": [v for f, v in zip(dias, acumulado(d["neto"] for d in dias.values())) if corte and f <= corte],
        "diario": [todos.get(corte - timedelta(days=i), VACIO)["neto"] for i in range(13, -1, -1)] if corte else [],
    }

    # ---------- Deudas con proveedores ----------
    facturas = Factura.query.options(joinedload(Factura.proveedor), selectinload(Factura.aplicaciones)).all()
    resumen = resumen_deudas(facturas)
    pagos_mes = Pago.query.filter(Pago.fecha >= inicio).all()
    agenda, n_agenda, total_agenda = proximos_pagos(facturas, hoy)
    proveedores = deuda_proveedores(facturas)

    # ---------- Clientes que no han vuelto ----------
    activos = {c.id: c for c in Cliente.query.filter_by(activo=True)}
    compras = (db.session.query(Venta.cliente_id, func.max(Venta.fecha), func.sum(NETO_SQL))
               .filter(Venta.cliente_id.isnot(None)).group_by(Venta.cliente_id).all())
    recuperar, n_recuperar = clientes_para_recuperar(
        [(activos[cid], ultima, total) for cid, ultima, total in compras if cid in activos], hoy, DIAS_SIN_COMPRA)

    # ---------- Publicidad del mes ----------
    ventas_redes = sum(r.neto for r in registros if r.medio_contacto in REDES_PAUTA)
    inversion = inversion_del_mes(InversionPublicidad.query.filter_by(mes=inicio).all(), inicio, hoy)
    publicidad = {"ventas": ventas_redes, "inversion": inversion,
                  "retorno": ventas_redes / inversion if inversion else None, "equilibrio": RETORNO_EQUILIBRIO}

    # ---------- Alertas: lo que hay que hacer hoy ----------
    # (tipo, icono, texto, valor, botón, enlace). Solo aparecen cuando hay algo que hacer.
    nombre_del_mes = nombre_mes(inicio).split()[0]
    alertas = []
    if resumen["n_vencidas"]:
        n = resumen["n_vencidas"]
        alertas.append(("peligro", "bi-exclamation-octagon", f"{_plural(n, 'factura')} vencida{'s' if n != 1 else ''}",
                        resumen["vencido"], "Ver", url_for("deudas.index", estado="vencida")))
    if resumen["n_por_vencer"]:
        n = resumen["n_por_vencer"]
        alertas.append(("aviso", "bi-calendar-event", f"{_plural(n, 'factura')} vence{'n' if n != 1 else ''} esta semana",
                        resumen["por_vencer"], "Ver", url_for("deudas.index", estado="por vencer")))
    if corte and (hoy - corte).days > 1:
        alertas.append(("aviso", "bi-cloud-arrow-up", f"Ventas cargadas hasta el {_fecha_corta(corte)}", None,
                        "Registrar", url_for("ventas.dia", fecha=(corte + timedelta(days=1)).isoformat())))
    elif not corte and hoy.day > 1:
        alertas.append(("aviso", "bi-cloud-arrow-up", f"{nombre_del_mes} aún no tiene ventas cargadas", None,
                        "Registrar", url_for("ventas.dia", fecha=inicio.isoformat())))
    if not meta:
        alertas.append(("info", "bi-bullseye", f"{nombre_del_mes} no tiene meta", None, "Definir", url_for("metas.index")))
    elif avance and avance["estado"] in ("en riesgo", "atrasada"):
        alertas.append(("aviso", "bi-graph-down-arrow", f"La meta va {avance['estado']}", None, "Ver ventas",
                        url_for("ventas.index")))
    sin_contacto = sum(1 for r in registros if not r.es_devolucion and not r.medio_contacto)
    if sin_contacto:
        alertas.append(("info", "bi-question-circle", f"{_plural(sin_contacto, 'venta')} sin medio de contacto", None,
                        "Revisar", url_for("ventas.index")))
    if n_recuperar:
        alertas.append(("info", "bi-person-heart", f"{_plural(n_recuperar, 'cliente')} sin volver hace +{DIAS_SIN_COMPRA} días",
                        None, "Contactar", "#recuperar"))

    return render_template(
        "dashboard/index.html",
        hoy=hoy, saludo=saludo(ahora.hour), nombre=(current_user.nombre or "").split()[0] if current_user.nombre else "",
        mes=nombre_del_mes, mes_anterior=nombre_mes(inicio_ant).split()[0],
        actual=actual, cambio_mes=variacion(actual["neto"], previo["neto"]), corte=corte, corte_ant=corte_ant,
        corte_texto=_fecha_corta(corte) if corte else None,
        ultimo=ultimo, promedio=promedio, cambio_dia=variacion(ultimo["neto"], promedio) if ultimo else None,
        meta=meta, avance=avance, cierre=cierre, grafica=grafica,
        resumen=resumen, abonado_mes=sum(p.valor for p in pagos_mes), n_abonos_mes=len(pagos_mes),
        agenda=agenda, n_agenda=n_agenda, total_agenda=total_agenda, proveedores=proveedores,
        recuperar=recuperar, n_recuperar=n_recuperar, dias_sin_compra=DIAS_SIN_COMPRA,
        publicidad=publicidad, alertas=alertas,
        ultimos_abonos=Pago.query.order_by(Pago.fecha.desc(), Pago.id.desc()).limit(4).all(),
    )


@bp.route("/aplicaciones")
def aplicaciones():
    """Todas las secciones del panel como íconos, al estilo del inicio de iCloud."""
    ahora = datetime.now(ZONA) if ZONA else datetime.now()
    return render_template("dashboard/aplicaciones.html", saludo=saludo(ahora.hour),
                           nombre=(current_user.nombre or "").split()[0] if current_user.nombre else "")


@bp.route("/buscar")
def buscar():
    """
    Resultados del buscador (Ctrl + K): clientes, proveedores, vendedoras y facturas.
    Las secciones del menú se buscan en el navegador; aquí solo van los datos,
    y solo para los roles que ven todo el panel.
    """
    from ...models import Proveedor, Vendedora
    from ...services.permisos import ve_todo
    from ...services.clientes import formato_telefono

    texto = " ".join(request.args.get("q", "").split())[:60]
    if not ve_todo() or len(texto) < 2:
        return jsonify(resultados=[])

    patron = f"%{texto}%"
    digitos = "".join(c for c in texto if c.isdigit())
    resultados = []

    for v in Vendedora.query.filter(Vendedora.nombre.ilike(patron)).order_by(Vendedora.nombre).limit(3):
        resultados.append({"grupo": "Vendedoras", "titulo": v.nombre, "icono": "users-round",
                           "detalle": "Activa" if v.activa else "Inactiva", "url": url_for("ventas.vendedoras")})

    for p in Proveedor.query.filter(Proveedor.nombre.ilike(patron)).order_by(Proveedor.nombre).limit(4):
        resultados.append({"grupo": "Proveedores", "titulo": p.nombre, "icono": "receipt-text",
                           "detalle": "Ver sus facturas", "url": url_for("deudas.index", proveedor=p.id)})

    filtro_cliente = Cliente.nombre.ilike(patron)
    if len(digitos) >= 4:
        filtro_cliente = filtro_cliente | Cliente.telefono.contains(digitos)
    for c in Cliente.query.filter(filtro_cliente).order_by(Cliente.nombre).limit(5):
        resultados.append({"grupo": "Clientes", "titulo": c.nombre, "icono": "contact-round",
                           "detalle": " · ".join(x for x in (formato_telefono(c.telefono) if c.telefono else "",
                                                          "Mayorista" if c.es_mayorista else "", c.ciudad or "") if x),
                           "url": url_for("clientes.detalle", id=c.id)})

    if digitos and digitos == texto.lstrip("#"):
        for v in Venta.query.filter(Venta.numero_factura == int(digitos)).limit(1):
            resultados.append({"grupo": "Facturas de venta", "titulo": f"Factura #{v.numero_factura}",
                               "icono": "shopping-bag", "detalle": f"{v.fecha.strftime('%d/%m/%Y')} · ${v.neto:,}".replace(",", "."),
                               "url": url_for("ventas.dia", fecha=v.fecha.isoformat())})
    for f in (Factura.query.options(joinedload(Factura.proveedor)).filter(Factura.numero.ilike(patron))
              .order_by(Factura.fecha_emision.desc()).limit(4)):
        resultados.append({"grupo": "Facturas de proveedores", "titulo": f"{f.proveedor.nombre} · {f.numero}",
                           "icono": "file-text", "detalle": f"Vence {f.fecha_limite.strftime('%d/%m/%Y')}",
                           "url": url_for("deudas.detalle", id=f.id)})
    return jsonify(resultados=resultados)
