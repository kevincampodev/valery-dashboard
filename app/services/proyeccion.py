import calendar
from datetime import timedelta


def promedio_por_dia_semana(ventas_por_fecha, hoy, semanas=8):
    """Promedio de ventas de lunes a domingo en las últimas `semanas` (sin contar hoy)."""
    sumas, conteos = [0] * 7, [0] * 7
    dia = hoy - timedelta(weeks=semanas)
    while dia < hoy:
        sumas[dia.weekday()] += ventas_por_fecha.get(dia, 0)
        conteos[dia.weekday()] += 1
        dia += timedelta(days=1)
    return [s // c if c else 0 for s, c in zip(sumas, conteos)]


def ocurrencias_gasto(frecuencia, dia_config, desde, hasta):
    """Fechas en que cae un gasto recurrente entre `desde` y `hasta` (ambas incluidas)."""
    fechas = []
    dia = desde
    while dia <= hasta:
        ultimo = calendar.monthrange(dia.year, dia.month)[1]
        if frecuencia == "semanal":
            cae = dia.weekday() == dia_config
        elif frecuencia == "quincenal":
            cae = dia.day in (15, ultimo)
        else:  # mensual: si el mes no tiene ese día (31 en septiembre), cae el último
            cae = dia.day == min(dia_config, ultimo)
        if cae:
            fechas.append(dia)
        dia += timedelta(days=1)
    return fechas


def flujo_semanal(hoy, semanas, saldo_inicial, promedios, factores_mes, escenario_pct,
                  facturas, gastos, liquidaciones, tasa_comision_bp):
    lunes = hoy - timedelta(days=hoy.weekday())
    fin_horizonte = lunes + timedelta(weeks=semanas, days=-1)
    filas = [{"inicio": lunes + timedelta(weeks=i), "fin": lunes + timedelta(weeks=i, days=6),
              "ventas": 0, "facturas": 0, "gastos": 0, "comisiones": 0} for i in range(semanas)]

    def semana(fecha):
        return max(0, (fecha - lunes).days // 7)   # lo vencido cae en la semana actual

    dia = hoy
    while dia <= fin_horizonte:
        venta = promedios[dia.weekday()] * factores_mes.get(dia.month, 100) * escenario_pct // 10000
        fila = filas[semana(dia)]
        fila["ventas"] += venta
        fila["comisiones"] += venta * tasa_comision_bp // 10000
        dia += timedelta(days=1)

    for f in facturas:
        if f.saldo > 0 and f.fecha_limite <= fin_horizonte:
            filas[semana(f.fecha_limite)]["facturas"] += f.saldo

    for g in gastos:
        for fecha in ocurrencias_gasto(g.frecuencia, g.dia, hoy, fin_horizonte):
            filas[semana(fecha)]["gastos"] += g.valor

    for liq in liquidaciones:
        if liq.fin <= fin_horizonte:
            filas[semana(liq.fin)]["comisiones"] += liq.total

    saldo = saldo_inicial
    for fila in filas:
        fila["salidas"] = fila["facturas"] + fila["gastos"] + fila["comisiones"]
        fila["neto"] = fila["ventas"] - fila["salidas"]
        fila["saldo_inicial"] = saldo
        saldo += fila["neto"]
        fila["saldo_final"] = saldo
    return filas


def proximos_pagos(hoy, dias, facturas, gastos, liquidaciones):
    """Agenda de todo lo que hay que pagar hasta dentro de `dias` días (incluye lo vencido)."""
    hasta = hoy + timedelta(days=dias)
    items = []
    for f in facturas:
        if f.saldo > 0 and f.fecha_limite <= hasta:
            items.append({"fecha": f.fecha_limite, "tipo": "Factura", "id": f.id,
                          "descripcion": f"{f.proveedor.nombre} · {f.numero}", "valor": f.saldo})
    for g in gastos:
        for fecha in ocurrencias_gasto(g.frecuencia, g.dia, hoy, hasta):
            items.append({"fecha": fecha, "tipo": "Gasto fijo", "id": g.id,
                          "descripcion": f"{g.nombre} ({g.categoria})", "valor": g.valor})
    for liq in liquidaciones:
        items.append({"fecha": liq.fin, "tipo": "Comisión", "id": liq.id,
                      "descripcion": f"Comisión {liq.vendedora.nombre}", "valor": liq.total})
    return sorted(items, key=lambda x: x["fecha"])