from datetime import date

from app.services.comisiones import quincena_de, calcular_comision


def test_quincenas_en_los_bordes():
    assert quincena_de(date(2026, 9, 15)) == (date(2026, 9, 1), date(2026, 9, 15))
    assert quincena_de(date(2026, 9, 16)) == (date(2026, 9, 16), date(2026, 9, 30))
    assert quincena_de(date(2026, 1, 31)) == (date(2026, 1, 16), date(2026, 1, 31))
    assert quincena_de(date(2026, 2, 20)) == (date(2026, 2, 16), date(2026, 2, 28))


def test_comision_con_meta_cumplida():
    r = calcular_comision(10_000_000, 200, 8_000_000, 100_000)   # 2% + bono
    assert r["comision"] == 200_000
    assert r["bono"] == 100_000
    assert r["total"] == 300_000
    assert r["cumple_meta"]


def test_comision_sin_meta_definida():
    r = calcular_comision(5_000_000, 150, None, 100_000)
    assert r["comision"] == 75_000
    assert r["bono"] == 0


def test_ventas_negativas_no_generan_comision_negativa():
    r = calcular_comision(-300_000, 200, None, 0)
    assert r["total"] == 0