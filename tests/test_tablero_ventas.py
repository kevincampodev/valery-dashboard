from datetime import date
from types import SimpleNamespace

from app.services.festivos import festivos, pascua, es_festivo
from app.services.tablero_ventas import (variacion, indicadores, por_dia, acumulado, proyeccion, calendario, ranking)


def test_festivos_de_colombia_2026():
    assert pascua(2026) == date(2026, 4, 5)
    esperados = {date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3),
                 date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 29),
                 date(2026, 7, 20), date(2026, 8, 7), date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2),
                 date(2026, 11, 16), date(2026, 12, 8), date(2026, 12, 25)}
    assert festivos(2026) == esperados
    assert es_festivo(date(2026, 11, 16)) and not es_festivo(date(2026, 11, 17))


def venta(dia, valor, canal="Minorista", prendas=1, devolucion=False):
    return SimpleNamespace(fecha=date(2026, 11, dia), valor=valor, canal=canal, prendas=prendas,
                           es_devolucion=devolucion, neto=-valor if devolucion else valor)


def test_indicadores_y_dias():
    regs = [venta(1, 100), venta(1, 300, "Mayorista", 3), venta(2, 50, devolucion=True), venta(3, 200)]
    assert indicadores(regs) == {"neto": 550, "minorista": 300, "mayorista": 300, "numero": 3, "prendas": 5}
    dias = por_dia(regs, date(2026, 11, 1), date(2026, 11, 30))
    assert len(dias) == 30 and dias[date(2026, 11, 1)]["numero"] == 2 and dias[date(2026, 11, 2)]["neto"] == -50
    assert dias[date(2026, 11, 16)]["festivo"] and dias[date(2026, 11, 1)]["domingo"]


def test_variacion_acumulado_y_proyeccion():
    assert variacion(120, 100) == 20 and variacion(80, 100) == -20 and variacion(5, 0) is None
    assert acumulado([1, 2, 3]) == [1, 3, 6]
    dias = por_dia([venta(1, 1_000_000), venta(2, 1_040_000)], date(2026, 11, 1), date(2026, 11, 4))
    linea, cierre = proyeccion(dias, date(2026, 11, 2), date(2026, 11, 4))
    assert linea == [None, 2_040_000, 3_060_000, 4_080_000]      # 1.020.000 por día durante 4 días
    assert cierre == 4_100_000                                   # redondeado a cientos de miles
    assert proyeccion(dias, date(2026, 11, 4), date(2026, 11, 4)) == ([None] * 4, None)   # mes cerrado


def test_calendario_empieza_el_dia_correcto():
    dias = por_dia([], date(2026, 11, 1), date(2026, 11, 30))     # 1 de noviembre de 2026 es domingo
    semanas = calendario(dias)
    assert semanas[0][:6] == [None] * 6 and semanas[0][6] == date(2026, 11, 1)
    assert all(len(s) == 7 for s in semanas)


def test_ranking_separa_apartes():
    grupos = {"Ana": {"valor": 300, "numero": 3}, "Al por mayor": {"valor": 600, "numero": 2},
              "Luz": {"valor": 100, "numero": 1}, "Vacía": {"valor": 0, "numero": 0}}
    principales, aparte = ranking(grupos, 1000, apartes=("Al por mayor",))
    assert [f["nombre"] for f in principales] == ["Ana", "Luz"] and principales[0]["porcentaje"] == 30
    assert aparte[0]["nombre"] == "Al por mayor"
