from datetime import date
from types import SimpleNamespace

from app.services.metas import avance_meta, calcular_incentivo

INICIO, FIN = date(2026, 9, 1), date(2026, 9, 30)
HOY = date(2026, 9, 24)  # 23 días terminados, 7 por vender (24 al 30)


def test_en_camino():
    a = avance_meta(23_000, 30_000, INICIO, FIN, HOY)
    assert a["ritmo_actual"] == 1_000
    assert a["proyeccion"] == 30_000
    assert a["estado"] == "en camino"
    assert a["ritmo_necesario"] == 1_000
    assert a["porcentaje"] == 77


def test_en_riesgo_justo_en_el_90():
    a = avance_meta(20_700, 30_000, INICIO, FIN, HOY)   # proyecta 27.000 = 90%
    assert a["estado"] == "en riesgo"


def test_atrasada_y_ritmo_redondea_hacia_arriba():
    a = avance_meta(10_000, 30_000, INICIO, FIN, HOY)
    assert a["estado"] == "atrasada"
    assert a["ritmo_necesario"] == 2_858                # 20.000 / 7 = 2857,14 -> 2858


def test_mes_terminado_sin_cumplir():
    a = avance_meta(25_000, 30_000, INICIO, FIN, date(2026, 10, 5))
    assert a["estado"] == "no cumplida"
    assert a["ritmo_necesario"] == 0                    # sin división por cero


TRAMOS = [
    SimpleNamespace(cumplimiento_min=90, tasa_bp=50, bono_fijo=0),
    SimpleNamespace(cumplimiento_min=100, tasa_bp=100, bono_fijo=0),
    SimpleNamespace(cumplimiento_min=110, tasa_bp=150, bono_fijo=200_000),
]


def test_incentivo_aplica_tramo_mas_alto_alcanzado():
    r = calcular_incentivo(31_000_000, 30_000_000, TRAMOS)
    assert r["tramo"].cumplimiento_min == 100
    assert r["bono"] == 310_000                         # 1% de 31M
    assert r["siguiente"].cumplimiento_min == 110
    assert r["falta_siguiente"] == 2_000_000            # 33M - 31M


def test_incentivo_sin_tramo():
    r = calcular_incentivo(20_000_000, 30_000_000, TRAMOS)
    assert r["tramo"] is None and r["bono"] == 0
    assert r["falta_siguiente"] == 7_000_000            # 27M - 20M