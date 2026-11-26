"""
Cálculos del tablero de Ventas diarias (sin consultas a la base: reciben datos ya leídos).
Así se pueden probar solos y la ruta queda corta.
"""
from datetime import timedelta

from .festivos import festivos

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def variacion(actual, anterior):
    """% de cambio frente al período anterior. None si antes no hubo nada con qué comparar."""
    if not anterior:
        return None
    return round((actual - anterior) * 100 / anterior)


def indicadores(registros):
    """Totales de un grupo de ventas: neto, detal, por mayor, número de ventas y prendas."""
    ventas = [r for r in registros if not r.es_devolucion]
    return {
        "neto": sum(r.neto for r in registros),
        "minorista": sum(r.valor for r in ventas if r.canal == "Minorista"),
        "mayorista": sum(r.valor for r in ventas if r.canal == "Mayorista"),
        "numero": len(ventas),
        "prendas": sum(r.prendas or 0 for r in ventas),
    }


def por_dia(registros, inicio, fin):
    """Una entrada por cada día del mes, con lo necesario para la gráfica y su recuadro al pasar el mouse."""
    feriados = festivos(inicio.year) | festivos(fin.year)
    dias = {}
    for i in range((fin - inicio).days + 1):
        dia = inicio + timedelta(days=i)
        dias[dia] = {"minorista": 0, "mayorista": 0, "neto": 0, "numero": 0, "prendas": 0,
                     "domingo": dia.weekday() == 6, "festivo": dia in feriados}
    for r in registros:
        d = dias[r.fecha]
        d["neto"] += r.neto
        if not r.es_devolucion:
            d["minorista" if r.canal == "Minorista" else "mayorista"] += r.valor
            d["numero"] += 1
            d["prendas"] += r.prendas or 0
    return dias


def acumulado(valores):
    total, salida = 0, []
    for v in valores:
        total += v
        salida.append(total)
    return salida


def proyeccion(dias, hasta, fin):
    """
    Línea punteada desde el último día con datos hasta fin de mes, al ritmo promedio de los días transcurridos.
    Devuelve (lista alineada con los días del mes —None donde no aplica—, valor proyectado al cierre).
    """
    fechas = list(dias)
    transcurridos = [f for f in fechas if f <= hasta]
    if not transcurridos or hasta >= fin:
        return [None] * len(fechas), None
    vendido = sum(dias[f]["neto"] for f in transcurridos)
    ritmo = vendido / len(transcurridos)
    salida = []
    for f in fechas:
        if f < hasta:
            salida.append(None)
        else:
            salida.append(round(vendido + ritmo * (f - hasta).days))
    return salida, round(salida[-1], -5)          # el cierre se redondea a cientos de miles: es una estimación


def calendario(dias):
    """Semanas (lunes a domingo) para el calendario de calor; None en las casillas fuera del mes."""
    fechas = list(dias)
    semanas, semana = [], [None] * fechas[0].weekday()
    for f in fechas:
        semana.append(f)
        if len(semana) == 7:
            semanas.append(semana)
            semana = []
    if semana:
        semanas.append(semana + [None] * (7 - len(semana)))
    return semanas


def ranking(grupos, total, apartes=()):
    """
    Lista ordenada [{nombre, valor, numero, porcentaje}] para las barras horizontales.
    Los nombres en 'apartes' (Al por mayor, Sin vendedora...) van al final, separados.
    """
    filas = [{"nombre": n, **d, "porcentaje": round(d["valor"] * 100 / total) if total else 0}
             for n, d in grupos.items() if d["valor"]]
    principales = sorted([f for f in filas if f["nombre"] not in apartes], key=lambda f: -f["valor"])
    resto = sorted([f for f in filas if f["nombre"] in apartes], key=lambda f: -f["valor"])
    return principales, resto
