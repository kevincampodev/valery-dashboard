"""
Cálculos de la página de Deudas (sin consultas a la base: reciben las facturas ya leídas).

Reglas para que las cifras sean exactas:
- Saldo = total - abonos aplicados (o 0 si se pagó de contado).
- Fecha límite = la pactada si existe; si no, la de la factura.
- Una factura queda pagada el día del último abono que la completó
  (si fue de contado, el día de emisión).
"""
import unicodedata

PESTANAS = {
    "pendientes": "Pendientes",
    "vencidas": "Vencidas",
    "pagadas": "Pagadas",
    "todas": "Todas",
}
ESTADOS = ["vencida", "por vencer", "al día", "pagada"]


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()


def fila(f, hoy):
    """Todo lo que la tabla necesita de una factura, calculado una sola vez."""
    saldo, abonado = f.saldo, (f.total if f.pagada_contado else f.abonado)
    fechas_abono = [a.pago.fecha for a in f.aplicaciones if a.pago is not None]
    if saldo > 0:
        fecha_pago = None
    elif f.pagada_contado:
        fecha_pago = f.fecha_emision
    else:
        fecha_pago = max(fechas_abono, default=None)
    dias = (f.fecha_limite - hoy).days
    if saldo == 0:
        estado = "pagada"
    elif dias < 0:
        estado = "vencida"
    elif dias <= 7:
        estado = "por vencer"
    else:
        estado = "al día"
    return {
        "factura": f, "id": f.id, "proveedor": f.proveedor.nombre, "proveedor_id": f.proveedor_id,
        "numero": f.numero, "etiqueta": f.etiqueta, "emision": f.fecha_emision,
        "limite": f.fecha_limite, "original": f.fecha_vencimiento if f.fecha_pactada else None,
        "total": f.total, "abonado": abonado, "saldo": saldo,
        "porcentaje": 100 if saldo == 0 else (abonado * 100 // f.total if f.total else 0),
        "dias": dias, "estado": estado, "fecha_pago": fecha_pago, "n_abonos": len(fechas_abono),
        "retraso": (fecha_pago - f.fecha_limite).days if fecha_pago else None,   # >0: se pagó tarde
        "contado": f.pagada_contado,
        "buscar": sin_tildes(f"{f.proveedor.nombre} {f.numero} {f.etiqueta or ''}"),
    }


def en_pestana(filas, pestana):
    if pestana == "vencidas":
        return [x for x in filas if x["estado"] == "vencida"]
    if pestana == "pagadas":
        return [x for x in filas if x["estado"] == "pagada"]
    if pestana == "pendientes":
        return [x for x in filas if x["saldo"] > 0]
    return list(filas)


def filtrar(filas, proveedor_id=None, estado="", texto="", mes=""):
    texto = sin_tildes(texto.strip())
    return [x for x in filas
            if (not proveedor_id or x["proveedor_id"] == proveedor_id)
            and (not estado or x["estado"] == estado)
            and (not texto or texto in x["buscar"])
            and (not mes or x["emision"].strftime("%Y-%m") == mes)]


def ordenar(filas):
    """Lo pendiente primero, de lo más urgente a lo más lejano; lo pagado después, de lo más reciente a lo más viejo."""
    pendientes = sorted((x for x in filas if x["saldo"] > 0), key=lambda x: (x["limite"], x["proveedor"]))
    pagadas = sorted((x for x in filas if x["saldo"] == 0),
                     key=lambda x: (x["fecha_pago"] or x["limite"]).toordinal(), reverse=True)
    return pendientes + pagadas


def resumen(filas):
    """Franja superior: siempre sobre todas las facturas, sin importar el filtro."""
    pendientes = [x for x in filas if x["saldo"] > 0]
    tramos = []
    for estado, nombre in (("vencida", "Vencido"), ("por vencer", "Vence en 7 días"), ("al día", "Al día")):
        grupo = [x for x in pendientes if x["estado"] == estado]
        tramos.append({"estado": estado, "nombre": nombre, "valor": sum(x["saldo"] for x in grupo), "numero": len(grupo)})
    deuda = sum(x["saldo"] for x in pendientes)
    for t in tramos:
        t["porcentaje"] = round(t["valor"] * 100 / deuda, 1) if deuda else 0
    return {"deuda": deuda, "numero": len(pendientes),
            "proveedores": len({x["proveedor_id"] for x in pendientes}), "tramos": tramos}


def totales(filas):
    return {"total": sum(x["total"] for x in filas), "abonado": sum(x["abonado"] for x in filas),
            "saldo": sum(x["saldo"] for x in filas), "numero": len(filas)}


def por_proveedor(filas):
    """Una entrada por proveedor con lo que se le debe; los que no tienen deuda van al final."""
    grupos = {}
    for x in filas:
        g = grupos.setdefault(x["proveedor_id"], {"id": x["proveedor_id"], "nombre": x["proveedor"], "facturas": [],
                                                  "total": 0, "abonado": 0, "saldo": 0, "pendientes": 0,
                                                  "mas_vencida": None, "estado": "pagada"})
        g["facturas"].append(x)
        g["total"] += x["total"]
        g["abonado"] += x["abonado"]
        g["saldo"] += x["saldo"]
        if x["saldo"] > 0:
            g["pendientes"] += 1
            if g["mas_vencida"] is None or x["dias"] < g["mas_vencida"]:
                g["mas_vencida"] = x["dias"]
    orden = {"vencida": 0, "por vencer": 1, "al día": 2, "pagada": 3}
    for g in grupos.values():
        g["facturas"] = ordenar(g["facturas"])
        g["estado"] = min((x["estado"] for x in g["facturas"]), key=orden.get)
        g["porcentaje"] = g["abonado"] * 100 // g["total"] if g["total"] else 0
    return sorted(grupos.values(), key=lambda g: (g["saldo"] == 0, -g["saldo"], g["nombre"]))


def meses_disponibles(filas):
    return sorted({x["emision"].strftime("%Y-%m") for x in filas}, reverse=True)
