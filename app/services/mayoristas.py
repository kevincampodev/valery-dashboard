from ..utils import a_pesos

UMBRAL_MAYORISTA_DEFECTO = 700_000


def es_mayorista(vende_mayorista, valor, umbral):
    """Regla del negocio: es mayorista si la hizo alguien con permiso mayorista Y pasa del umbral en una sola venta."""
    return bool(vende_mayorista) and valor > umbral


def normalizar_referencia(texto):
    """'09176' -> '9176' | ' vestido  largo ' -> 'VESTIDO LARGO'"""
    limpio = " ".join(str(texto or "").split()).upper()
    if limpio.isdigit():
        limpio = limpio.lstrip("0") or "0"
    return limpio


def leer_lineas(referencias, cantidades, precios):
    """Convierte las listas del formulario en líneas de venta. Devuelve (lineas, errores)."""
    lineas, errores = [], []
    for n, (ref, cant, precio) in enumerate(zip(referencias, cantidades, precios), start=1):
        referencia = normalizar_referencia(ref)
        texto_cantidad = str(cant or "").strip()
        cantidad = int(texto_cantidad) if texto_cantidad.isdigit() else 0
        precio_unitario = a_pesos(precio)
        if not referencia and not texto_cantidad and not precio_unitario:
            continue
        if not referencia or cantidad <= 0 or precio_unitario <= 0:
            errores.append(f"Línea {n}: referencia, cantidad y precio unitario son obligatorios.")
            continue
        lineas.append({"referencia": referencia, "cantidad": cantidad, "precio_unitario": precio_unitario})
    return lineas, errores


def total_lineas(lineas):
    return sum(l["cantidad"] * l["precio_unitario"] for l in lineas)


def historial_precios(registros):
    """Resumen de precios por referencia: último precio (con fecha y cliente), promedio ponderado, mínimo y máximo."""
    por_referencia = {}
    for r in sorted(registros, key=lambda r: r.fecha):
        h = por_referencia.setdefault(r.referencia, {"unidades": 0, "total": 0, "minimo": None, "maximo": None})
        h["unidades"] += r.cantidad
        h["total"] += r.cantidad * r.precio_unitario
        h["minimo"] = r.precio_unitario if h["minimo"] is None else min(h["minimo"], r.precio_unitario)
        h["maximo"] = r.precio_unitario if h["maximo"] is None else max(h["maximo"], r.precio_unitario)
        h["ultimo"], h["fecha_ultimo"], h["cliente_ultimo"] = r.precio_unitario, r.fecha, r.cliente
    for h in por_referencia.values():
        h["promedio"] = h["total"] // h["unidades"]
    return dict(sorted(por_referencia.items()))