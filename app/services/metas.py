def avance_meta(vendido, meta, inicio, fin, hoy):
    """
    Calcula el avance de una meta mensual.
    Convención: 'hoy' todavía cuenta como día por vender; los días transcurridos
    son los que ya terminaron.
    """
    dias_mes = (fin - inicio).days + 1
    if hoy < inicio:
        transcurridos, restantes = 0, dias_mes
    elif hoy > fin:
        transcurridos, restantes = dias_mes, 0
    else:
        transcurridos, restantes = (hoy - inicio).days, (fin - hoy).days + 1

    faltante = max(meta - vendido, 0)
    ritmo_actual = vendido // transcurridos if transcurridos else 0
    proyeccion = vendido + ritmo_actual * restantes

    if vendido >= meta:
        estado = "cumplida"
    elif restantes == 0:
        estado = "no cumplida"
    elif transcurridos == 0:
        estado = "por iniciar"
    elif proyeccion >= meta:
        estado = "en camino"
    elif proyeccion >= meta * 9 // 10:
        estado = "en riesgo"
    else:
        estado = "atrasada"

    return {
        "meta": meta,
        "vendido": vendido,
        "porcentaje": round(vendido * 100 / meta) if meta else 0,
        "faltante": faltante,
        "dias_restantes": restantes,
        "ritmo_necesario": -(-faltante // restantes) if restantes else 0,  # división hacia arriba
        "ritmo_actual": ritmo_actual,
        "proyeccion": proyeccion,
        "estado": estado,
    }


def calcular_incentivo(vendido, meta, tramos):
    """Aplica el tramo más alto alcanzado según el % de cumplimiento de la meta."""
    cumplimiento = vendido * 100 / meta if meta else 0
    alcanzado, siguiente = None, None
    for tramo in sorted(tramos, key=lambda t: t.cumplimiento_min):
        if cumplimiento >= tramo.cumplimiento_min:
            alcanzado = tramo
        elif siguiente is None:
            siguiente = tramo

    bono = (vendido * alcanzado.tasa_bp // 10000 + alcanzado.bono_fijo) if alcanzado else 0
    falta_siguiente = ((meta * siguiente.cumplimiento_min + 99) // 100 - vendido) if siguiente else 0

    return {
        "cumplimiento": round(cumplimiento, 1),
        "tramo": alcanzado,
        "bono": bono,
        "siguiente": siguiente,
        "falta_siguiente": falta_siguiente,
    }