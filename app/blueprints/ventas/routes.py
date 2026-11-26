from datetime import date, datetime, timedelta

from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from . import bp
from ...extensions import db
from ...models import (Venta, Vendedora, Parametro, LineaVenta, Cliente, Meta, CANALES, MEDIOS_VENTA,
                      MEDIOS_CONTACTO)
from ...services.clientes import normalizar_telefono, formato_telefono
from ...services.mayoristas import es_mayorista, total_lineas, UMBRAL_MAYORISTA_DEFECTO
from ...services.detalle_venta import leer_detalle

TALLAS_BASE = ["XS", "S", "M", "L", "XL", "XXL", "ÚNICA"]


def _resolver_cliente(telefono_texto, nombre, autoriza):
    """
    Devuelve (cliente, error). Sin datos del cliente devuelve (None, None): es opcional.
    Solo se guarda si hay teléfono válido y autorización de datos.
    """
    telefono_texto = (telefono_texto or "").strip()
    nombre = " ".join((nombre or "").split())[:120]
    if not telefono_texto and not nombre:
        return None, None
    if not telefono_texto:
        return None, "para guardar al cliente hace falta su teléfono."
    if not autoriza:
        return None, "marca la autorización de datos del cliente, o borra sus datos."
    telefono = normalizar_telefono(telefono_texto)
    if not telefono:
        return None, "el teléfono del cliente no es válido (deben ser 10 dígitos)."

    cliente = Cliente.query.filter_by(telefono=telefono).first()
    if cliente:
        if nombre and cliente.nombre.startswith("Cliente "):
            cliente.nombre = nombre
        if not cliente.autoriza_datos:
            cliente.autoriza_datos = True
            cliente.fecha_autorizacion = datetime.now()
        return cliente, None

    cliente = Cliente(nombre=nombre or f"Cliente {formato_telefono(telefono)}", telefono=telefono,
                      es_mayorista=False, autoriza_datos=True, fecha_autorizacion=datetime.now())
    db.session.add(cliente)
    return cliente, None
from ...services.ventas import resumen_mes
from ...services.metas import avance_meta
from ...services.tablero_ventas import (DIAS_SEMANA, variacion, indicadores, por_dia, acumulado, proyeccion,
                                        calendario, ranking)
from ...utils import a_pesos, a_fecha, formato_pesos, mes_desde_texto, rango_mes, nombre_mes


@bp.route("/")
def index():
    hoy = date.today()
    inicio, fin = rango_mes(mes_desde_texto(request.args.get("mes")))
    registros = (Venta.query.options(joinedload(Venta.vendedora), selectinload(Venta.pagos))
                 .filter(Venta.fecha.between(inicio, fin)).all())
    resumen = resumen_mes(registros, inicio, fin)
    dias = por_dia(registros, inicio, fin)

    # Corte = último día con ventas cargadas (si el mes ya pasó, el último día del mes).
    # Comparar contra "hoy" sería injusto cuando las facturas se cargan con unos días de atraso.
    if fin < hoy:
        corte = fin
    else:
        corte = max((r.fecha for r in registros), default=None)

    # Mes anterior: mismos días para las tarjetas y el mes completo para la línea del acumulado
    fin_ant = inicio - timedelta(days=1)
    inicio_ant = fin_ant.replace(day=1)
    anteriores = Venta.query.filter(Venta.fecha.between(inicio_ant, fin_ant)).all()
    if corte:
        corte_ant = inicio_ant.replace(day=min(corte.day, fin_ant.day))
        comparables = [r for r in anteriores if r.fecha <= corte_ant]
    else:
        corte_ant, comparables = None, []
    actual, previo = indicadores(registros), indicadores(comparables)
    cambios = {k: variacion(actual[k], previo[k]) for k in actual}

    # Meta del mes (la misma que se define en Metas)
    meta = Meta.query.filter_by(periodo=inicio, canal="Total").first()
    avance = None
    if meta and corte:
        avance = avance_meta(actual["neto"], meta.valor, inicio, fin, min(corte + timedelta(days=1), fin + timedelta(days=1)))

    # Acumulado del mes, mes anterior, meta y proyección de cierre
    fechas = list(dias)
    netos = [dias[f]["neto"] for f in fechas]
    acum = acumulado(netos)
    if corte:
        acum = [v if f <= corte else None for f, v in zip(fechas, acum)]
    dias_ant = por_dia(anteriores, inicio_ant, fin_ant)
    acum_ant = acumulado([d["neto"] for d in dias_ant.values()])
    acum_ant = [acum_ant[i] if i < len(acum_ant) else None for i in range(len(fechas))]
    linea_meta = [round(meta.valor * (i + 1) / len(fechas)) for i in range(len(fechas))] if meta else None
    linea_proy, cierre = proyeccion(dias, corte, fin) if corte else ([None] * len(fechas), None)

    # Medio de pago: con el desglose de los pagos mixtos cuando existe
    por_medio = {}
    for r in registros:
        if r.es_devolucion or not r.pagos:
            por_medio[r.medio_pago] = por_medio.get(r.medio_pago, 0) + r.neto
        else:
            for p in r.pagos:
                por_medio[p.medio] = por_medio.get(p.medio, 0) + p.valor

    grupos_vend, grupos_cont, grupos_medio = {}, {}, {}
    for r in registros:
        nombre = r.vendedora.nombre if r.vendedora else "Sin vendedora"
        contacto = r.medio_contacto or "Sin dato"
        for grupos, clave in ((grupos_vend, nombre), (grupos_cont, contacto)):
            g = grupos.setdefault(clave, {"valor": 0, "numero": 0})
            g["valor"] += r.neto
            g["numero"] += 0 if r.es_devolucion else 1
    for medio, valor in por_medio.items():
        grupos_medio[medio] = {"valor": valor, "numero": None}
    total = actual["neto"]
    vendedoras, vendedoras_aparte = ranking(grupos_vend, total, apartes=("Al por mayor", "Sin vendedora"))
    medios, _ = ranking(grupos_medio, total)
    contactos, contactos_aparte = ranking(grupos_cont, total, apartes=("Sin dato",))

    top = (db.session.query(LineaVenta.referencia, func.max(LineaVenta.descripcion),
                            func.sum(LineaVenta.cantidad), func.sum(LineaVenta.cantidad * LineaVenta.precio_unitario))
           .join(Venta).filter(Venta.fecha.between(inicio, fin), Venta.es_devolucion.is_(False))
           .group_by(LineaVenta.referencia).order_by(func.sum(LineaVenta.cantidad).desc()).limit(5).all())

    grafica = {
        "dias": [{"etiqueta": f.strftime("%d"), "semana": DIAS_SEMANA[f.weekday()], "fecha": f.isoformat(),
                  "url": url_for("ventas.dia", fecha=f.isoformat()), "hoy": f == hoy, **d} for f, d in dias.items()],
        "acumulado": acum, "anterior": acum_ant, "meta": linea_meta, "proyeccion": linea_proy,
        "nombre_anterior": nombre_mes(inicio_ant).split()[0],
    }
    maximo_dia = max((d["neto"] for d in dias.values()), default=0)

    return render_template(
        "ventas/index.html",
        r=resumen, actual=actual, cambios=cambios, corte=corte, corte_ant=corte_ant,
        meta=meta, avance=avance, cierre=cierre, grafica=grafica, dias=dias, maximo_dia=maximo_dia,
        semanas=calendario(dias), dias_semana=DIAS_SEMANA,
        vendedoras=vendedoras, vendedoras_aparte=vendedoras_aparte, medios=medios,
        contactos=contactos, contactos_aparte=contactos_aparte, top=top,
        titulo=nombre_mes(inicio), mes_anterior=nombre_mes(inicio_ant),
        anterior=(inicio - timedelta(days=1)).strftime("%Y-%m"),
        siguiente=(fin + timedelta(days=1)).strftime("%Y-%m"),
        hoy=hoy,
    )


@bp.route("/dia/<fecha>", methods=["GET", "POST"])
def dia(fecha):
    try:
        fecha_venta = date.fromisoformat(fecha)
    except ValueError:
        abort(404)

    vendedoras = Vendedora.query.filter_by(activa=True).order_by(Vendedora.nombre).all()
    ids_validos = {v.id for v in vendedoras}
    ids_mayoristas = {v.id for v in vendedoras if v.vende_mayorista}
    umbral = Parametro.obtener_int("umbral_mayorista", UMBRAL_MAYORISTA_DEFECTO)

    if request.method == "POST":
        f = request.form
        filas = zip(f.getlist("vendedora_id"), f.getlist("medio_pago"), f.getlist("tipo"), f.getlist("valor"),
                    f.getlist("prendas"), f.getlist("medio_contacto"), f.getlist("detalle"),
                    f.getlist("cliente_telefono"), f.getlist("cliente_nombre"), f.getlist("cliente_autoriza"))

        nuevas, errores = [], []
        for n, (vendedora_id, medio, tipo, valor, prendas, contacto, detalle,
                telefono_cliente, nombre_cliente, autoriza) in enumerate(filas, start=1):
            cantidad_prendas = int(prendas) if prendas.isdigit() else 0
            lineas, error_detalle = leer_detalle(detalle, cantidad_prendas)
            if error_detalle:
                errores.append(f"Fila {n}: {error_detalle}")
                continue
            valor = total_lineas(lineas) if lineas else a_pesos(valor)
            if valor <= 0:
                continue  # fila vacía: se ignora
            vendedora_id = int(vendedora_id) if vendedora_id else None
            if contacto not in MEDIOS_CONTACTO:
                errores.append(f"Fila {n}: falta el medio de contacto.")
                continue
            if tipo != "devolucion" and es_mayorista(vendedora_id in ids_mayoristas, valor, umbral):
                errores.append(f"Fila {n}: venta de {formato_pesos(valor)} hecha por quien vende al por mayor. "
                               f"Es mayorista: regístrala en Mayoristas → Nueva venta.")
                continue
            if medio not in MEDIOS_VENTA or (vendedora_id and vendedora_id not in ids_validos):
                errores.append(f"Fila {n}: datos inválidos.")
                continue
            cliente, error_cliente = _resolver_cliente(telefono_cliente, nombre_cliente, autoriza == "1")
            if error_cliente:
                errores.append(f"Fila {n}: {error_cliente}")
                continue
            venta = Venta(
                fecha=fecha_venta, canal="Minorista", vendedora_id=vendedora_id, medio_pago=medio, cliente=cliente,
                valor=valor, prendas=int(prendas) if prendas.isdigit() else None, medio_contacto=contacto,
                es_devolucion=(tipo == "devolucion"),
            )
            venta.lineas.extend(LineaVenta(**linea) for linea in lineas)
            nuevas.append(venta)

        if errores:
            for e in errores:
                flash(e, "danger")
        elif not nuevas:
            flash("No había filas con valor para guardar.", "warning")
        else:
            db.session.add_all(nuevas)
            db.session.commit()
            flash(f"{len(nuevas)} registros guardados. Neto: {formato_pesos(sum(v.neto for v in nuevas))}.", "success")
        return redirect(url_for("ventas.dia", fecha=fecha))

    registros = (Venta.query.options(joinedload(Venta.vendedora), joinedload(Venta.cliente), selectinload(Venta.lineas),
                                     selectinload(Venta.pagos))
                 .filter_by(fecha=fecha_venta)
                 # En el orden del talonario; las registradas a mano (sin número) van al final
                 .order_by(Venta.numero_factura.is_(None), Venta.numero_factura, Venta.id).all())

    tallas_usadas = [t for (t,) in db.session.query(LineaVenta.talla)
                     .filter(LineaVenta.talla.isnot(None)).distinct()]
    sugerencias = {
        "referencias": [r for (r,) in db.session.query(LineaVenta.referencia)
                        .distinct().order_by(LineaVenta.referencia).limit(500)],
        "colores": [c for (c,) in db.session.query(LineaVenta.color)
                    .filter(LineaVenta.color.isnot(None)).distinct().order_by(LineaVenta.color)],
        "tallas": TALLAS_BASE + sorted(t for t in tallas_usadas if t not in TALLAS_BASE),
    }
    return render_template(
        "ventas/dia.html",
        fecha_venta=fecha_venta,
        registros=registros,
        total=sum(r.neto for r in registros),
        vendedoras=vendedoras,
        canales=["Minorista"],
        medios=MEDIOS_VENTA,
        contactos=MEDIOS_CONTACTO,
        umbral=umbral,
        sugerencias=sugerencias,
        detalles={v.id: _detalle_venta(v) for v in registros},
        anterior=(fecha_venta - timedelta(days=1)).isoformat(),
        siguiente=(fecha_venta + timedelta(days=1)).isoformat(),
    )


@bp.route("/<int:id>/eliminar", methods=["POST"])
def eliminar(id):
    venta = db.get_or_404(Venta, id)
    fecha = venta.fecha.isoformat()
    db.session.delete(venta)
    db.session.commit()
    flash("Registro eliminado.", "info")
    return redirect(url_for("ventas.dia", fecha=fecha))


@bp.route("/vendedoras", methods=["GET", "POST"])
def vendedoras():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre es obligatorio.", "danger")
        else:
            db.session.add(Vendedora(nombre=nombre, fecha_ingreso=a_fecha(request.form.get("fecha_ingreso"))))
            try:
                db.session.commit()
                flash(f"Vendedora {nombre} creada.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("Ya existe una vendedora con ese nombre.", "danger")
        return redirect(url_for("ventas.vendedoras"))

    lista = Vendedora.query.order_by(Vendedora.activa.desc(), Vendedora.nombre).all()
    return render_template("ventas/vendedoras.html", vendedoras=lista)


@bp.route("/vendedoras/<int:id>/estado", methods=["POST"])
def cambiar_estado(id):
    vendedora = db.get_or_404(Vendedora, id)
    vendedora.activa = not vendedora.activa
    db.session.commit()
    flash(f"{vendedora.nombre} ahora está {'activa' if vendedora.activa else 'inactiva'}.", "info")
    return redirect(url_for("ventas.vendedoras"))


@bp.route("/vendedoras/<int:id>/mayorista", methods=["POST"])
def cambiar_mayorista(id):
    vendedora = db.get_or_404(Vendedora, id)
    vendedora.vende_mayorista = not vendedora.vende_mayorista
    db.session.commit()
    estado = "ahora puede" if vendedora.vende_mayorista else "ya no puede"
    flash(f"{vendedora.nombre} {estado} registrar ventas mayoristas.", "info")
    return redirect(url_for("ventas.vendedoras"))


@bp.route("/cliente")
def buscar_cliente():
    """JSON con los datos de un cliente por teléfono, para autocompletar el formulario."""
    telefono = normalizar_telefono(request.args.get("telefono"))
    if not telefono:
        return jsonify({"valido": False})
    cliente = Cliente.query.filter_by(telefono=telefono).first()
    if not cliente:
        return jsonify({"valido": True, "encontrado": False})
    compras, ultima = (db.session.query(func.count(Venta.id), func.max(Venta.fecha))
                       .filter(Venta.cliente_id == cliente.id).one())
    return jsonify({
        "valido": True,
        "encontrado": True,
        "nombre": cliente.nombre,
        "compras": compras,
        "ultima": ultima.strftime("%d/%m/%Y") if ultima else None,
        "autorizado": cliente.autoriza_datos,
    })


def _detalle_venta(venta):
    """Toda la información de una venta guardada, para mostrarla en el recuadro de detalle."""
    if venta.numero_factura:
        hora = f"Factura #{venta.numero_factura}"
    else:
        hora = venta.creado_en.strftime("%I:%M %p") if venta.creado_en else ""
    medio = venta.medio_pago
    if len(venta.pagos) > 1:
        medio = " + ".join(f"{p.medio} {formato_pesos(p.valor)}" for p in venta.pagos)
    return {
        "hora": hora,
        "cliente": venta.cliente.nombre if venta.cliente else None,
        "telefono": formato_telefono(venta.cliente.telefono) if venta.cliente else None,
        "vendedora": venta.vendedora.nombre if venta.vendedora else "Sin vendedora",
        "medio": medio,
        "contacto": venta.medio_contacto or "—",
        "tipo": "Devolución" if venta.es_devolucion else "Venta",
        "valor": venta.valor,
        "prendas": venta.prendas,
        "lineas": [{
            "referencia": f"{l.referencia} · {l.descripcion}" if l.descripcion and l.descripcion != l.referencia
            else l.referencia,
            "color": l.color or "", "talla": l.talla or "",
            "cantidad": l.cantidad, "precio": l.precio_unitario, "subtotal": l.subtotal,
        } for l in venta.lineas],
    }