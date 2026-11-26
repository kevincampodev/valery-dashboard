"""
Festivos de Colombia (Ley 51 de 1983, "Ley Emiliani"), calculados para cualquier año.

- Fijos: se celebran el mismo día aunque caigan entre semana.
- Trasladables: se pasan al lunes siguiente si no caen en lunes.
- Los de Semana Santa dependen de la fecha de la Pascua.
"""
from datetime import date, timedelta

FIJOS = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
TRASLADABLES = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]


def pascua(anio):
    """Domingo de Pascua (algoritmo de Meeus/Jones/Butcher para el calendario gregoriano)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def _al_lunes(dia):
    return dia + timedelta(days=(7 - dia.weekday()) % 7)


def festivos(anio):
    domingo = pascua(anio)
    dias = {date(anio, m, d) for m, d in FIJOS}
    dias |= {_al_lunes(date(anio, m, d)) for m, d in TRASLADABLES}
    dias |= {domingo - timedelta(days=3), domingo - timedelta(days=2)}       # jueves y viernes santo
    dias |= {domingo + timedelta(days=n) for n in (43, 64, 71)}              # Ascensión, Corpus, Sagrado Corazón
    return dias


def es_festivo(dia):
    return dia in festivos(dia.year)
