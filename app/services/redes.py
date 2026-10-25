"""Cálculos de ventas por redes sociales para el equipo de marketing (sin datos de clientes ni márgenes)."""
import calendar
from datetime import date

from .marketing import REDES_PAUTA

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def periodo_comparable(inicio, fin, hoy):
    """
    Rango del mes anterior con el que se compara.
    Si el mes va en curso (ej. hoy 24 de octubre), se compara con los mismos días del mes anterior
    (1 al 24 de septiembre); comparar 24 días contra un mes completo siempre daría "bajó".
    """
    fin_anterior = inicio.replace(day=1) - date.resolution
    inicio_anterior = fin_anterior.replace(day=1)
    if inicio <= hoy <= fin:
        dia = min(hoy.day, calendar.monthrange(inicio_anterior.year, inicio_anterior.month)[1])
        fin_anterior = inicio_anterior.replace(day=dia)
    return inicio_anterior, fin_anterior


def variacion(actual, anterior):
    """Porcentaje de cambio. None si antes no había nada con qué comparar."""
    if not anterior:
        return None
    return round((actual - anterior) * 100 / anterior)


def resumen_por_red(ventas, ventas_anteriores):
    """ventas: lista de (red, valor neto). Devuelve {red: {...}} más una fila 'Total'."""
    def agrupar(lista):
        datos = {red: {"total": 0, "numero": 0} for red in REDES_PAUTA}
        for red, valor in lista:
            if red in datos:
                datos[red]["total"] += valor
                datos[red]["numero"] += 1
        datos["Total"] = {"total": sum(d["total"] for d in datos.values()),
                          "numero": sum(d["numero"] for d in datos.values())}
        return datos

    actual, anterior = agrupar(ventas), agrupar(ventas_anteriores)
    for red, d in actual.items():
        d["promedio"] = d["total"] // d["numero"] if d["numero"] else 0
        d["anterior"] = anterior[red]["total"]
        d["variacion"] = variacion(d["total"], anterior[red]["total"])
        d["variacion_numero"] = variacion(d["numero"], anterior[red]["numero"])
    return actual


def por_dia_semana(ventas):
    """ventas: lista de (fecha, red, valor). Devuelve {red: [lunes..domingo]}."""
    series = {red: [0] * 7 for red in REDES_PAUTA}
    for fecha, red, valor in ventas:
        if red in series:
            series[red][fecha.weekday()] += valor
    return series


def clientes_nuevos(ventas, primera_compra, inicio):
    """
    ventas: lista de (cliente_id o None, red). primera_compra: {cliente_id: fecha de su primera compra}.
    Un cliente es nuevo si su primera compra fue en este mes. Se cuenta cada cliente una sola vez.
    """
    conteo = {red: {"nuevos": 0, "repiten": 0, "sin_dato": 0} for red in REDES_PAUTA}
    vistos = set()
    for cliente_id, red in ventas:
        if red not in conteo:
            continue
        if not cliente_id:
            conteo[red]["sin_dato"] += 1
            continue
        if cliente_id in vistos:
            continue
        vistos.add(cliente_id)
        primera = primera_compra.get(cliente_id)
        conteo[red]["nuevos" if primera and primera >= inicio else "repiten"] += 1
    return conteo
