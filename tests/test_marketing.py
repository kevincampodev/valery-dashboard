from datetime import date

from app.services.marketing import meses_entre, dias_pauta, retorno_equilibrio, rentabilidad
from app.utils import formato_pesos

HOY = date(2026, 9, 29)


def test_meses_entre_cruza_el_anio():
    assert meses_entre(date(2026, 11, 15), date(2027, 2, 1)) == [
        date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1), date(2027, 2, 1)]


def test_dias_de_pauta():
    assert dias_pauta(date(2026, 7, 1), None, HOY) == 31      # mes completo
    assert dias_pauta(date(2026, 7, 1), 10, HOY) == 10        # pauta pausada parte del mes
    assert dias_pauta(date(2026, 9, 1), None, HOY) == 29      # mes en curso: hasta hoy
    assert dias_pauta(date(2026, 10, 1), None, HOY) == 0      # mes futuro


def test_vender_mas_de_lo_invertido_no_es_ganar():
    r = rentabilidad(6_000_000, 3_600_000, 0, 5000)
    assert r["retorno"] == 1.67
    assert r["ganancia_bruta"] == 3_000_000
    assert r["resultado"] == -600_000
    assert r["estado"] == "pérdida"
    assert retorno_equilibrio(5000) == 2.0


def test_mes_sin_pauta_no_divide_por_cero():
    r = rentabilidad(85_000, 0, 0, 5000)
    assert r["retorno"] is None and r["estado"] == "sin pauta"


def test_formato_pesos_negativos():
    assert formato_pesos(-2_792_500) == "-$2.792.500"
    assert formato_pesos(1500) == "$1.500"