"""
Cálculos de la página de Inicio (sin consultas a la base: reciben datos ya leídos).
Así se pueden probar solos y la ruta queda corta.
"""
from urllib.parse import quote

MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def saludo(hora):
    if hora < 12:
        return "Buenos días"
    if hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def proximos_pagos(facturas, hoy, limite=8, horizonte=30):
    """
    Agenda de pagos: primero lo vencido (lo más viejo arriba) y luego lo que vence en los próximos
    `horizonte` días. Cada fila trae la urgencia para pintarla: vencida, esta semana o más adelante.
    """
    pendientes = sorted((f for f in facturas if f.saldo > 0), key=lambda f: f.fecha_limite)
    filas = []
    for f in pendientes:
        dias = (f.fecha_limite - hoy).days
        if dias > horizonte:
            break
        urgencia = "vencida" if dias < 0 else ("pronto" if dias <= 7 else "normal")
        filas.append({"factura": f, "dias": dias, "urgencia": urgencia,
                      "dia": f.fecha_limite.day, "mes": MESES_CORTOS[f.fecha_limite.month - 1]})
    total = sum(x["factura"].saldo for x in filas)
    return filas[:limite], len(filas), total


def deuda_proveedores(facturas):
    """[{id, nombre, valor, numero, porcentaje}] de mayor a menor deuda, para las barras."""
    grupos = {}
    for f in facturas:
        if f.saldo > 0:
            g = grupos.setdefault(f.proveedor_id, {"id": f.proveedor_id, "nombre": f.proveedor.nombre,
                                                   "valor": 0, "numero": 0})
            g["valor"] += f.saldo
            g["numero"] += 1
    total = sum(g["valor"] for g in grupos.values())
    filas = sorted(grupos.values(), key=lambda g: -g["valor"])
    for g in filas:
        g["porcentaje"] = round(g["valor"] * 100 / total) if total else 0
    return filas


def enlace_whatsapp(telefono, nombre):
    """Enlace wa.me con un mensaje listo. None si el teléfono no es un celular colombiano de 10 dígitos."""
    digitos = "".join(c for c in (telefono or "") if c.isdigit())
    if len(digitos) == 12 and digitos.startswith("57"):
        digitos = digitos[2:]
    if len(digitos) != 10 or not digitos.startswith("3"):
        return None
    primero = (nombre or "").split()[0].capitalize() if nombre and not nombre.startswith("Cliente ") else ""
    mensaje = (f"Hola{' ' + primero if primero else ''}, te saludamos de Dany Fashion. "
               "Nos llegó mercancía nueva y nos acordamos de ti. ¿Te enviamos el catálogo?")
    return f"https://wa.me/57{digitos}?text={quote(mensaje)}"


def clientes_para_recuperar(compras, hoy, dias=45, limite=5):
    """
    compras: lista de (cliente, fecha_ultima_compra, total_comprado).
    Los que llevan más de `dias` sin comprar, empezando por los que más compraban
    (son los que más pesa perder). Devuelve (primeros `limite`, cuántos hay en total).
    """
    frios = [{"cliente": c, "ultima": u, "total": t or 0, "dias": (hoy - u).days,
              "whatsapp": enlace_whatsapp(c.telefono, c.nombre)}
             for c, u, t in compras if u and (hoy - u).days > dias]
    frios.sort(key=lambda x: (-x["total"], -x["dias"]))
    return frios[:limite], len(frios)
