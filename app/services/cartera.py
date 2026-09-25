RANGOS = ["Al día", "1-30", "31-60", "61-90", "+90"]


def rango_edad(dias_para_vencer):
    if dias_para_vencer >= 0:
        return "Al día"
    vencida = -dias_para_vencer
    if vencida <= 30:
        return "1-30"
    if vencida <= 60:
        return "31-60"
    if vencida <= 90:
        return "61-90"
    return "+90"


def cartera_por_edades(facturas):
    """Agrupa los saldos por proveedor y por rango de días vencidos."""
    columnas = RANGOS + ["Total"]
    filas, totales = {}, dict.fromkeys(columnas, 0)

    for f in facturas:
        if f.saldo <= 0:
            continue
        fila = filas.setdefault(f.proveedor.nombre, dict.fromkeys(columnas, 0))
        rango = rango_edad(f.dias_para_vencer)
        for acumulado in (fila, totales):
            acumulado[rango] += f.saldo
            acumulado["Total"] += f.saldo

    ordenadas = dict(sorted(filas.items(), key=lambda x: -x[1]["Total"]))
    return ordenadas, totales