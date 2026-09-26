from datetime import date
from types import SimpleNamespace

from app.services.proyeccion import ocurrencias_gasto, promedio_por_dia_semana, flujo_semanal

LUNES = date(2026, 9, 28)


def test_gasto_mensual_dia_31_cae_el_ultimo_del_mes():
    fechas = ocurrencias_gasto("mensual", 31, date(2026, 9, 1), date(2026, 10, 31))
    assert fechas == [date(2026, 9, 30), date(2026, 10, 31)]


def test_gasto_quincenal_y_semanal():
    assert ocurrencias_gasto("quincenal", 1, date(2026, 2, 1), date(2026, 2, 28)) == [date(2026, 2, 15), date(2026, 2, 28)]
    assert ocurrencias_gasto("semanal", 0, date(2026, 9, 28), date(2026, 10, 11)) == [date(2026, 9, 28), date(2026, 10, 5)]


def test_promedio_por_dia_de_la_semana():
    ventas = {date(2026, 9, 21): 700, date(2026, 9, 26): 100}   # lunes y sábado
    promedios = promedio_por_dia_semana(ventas, LUNES, semanas=1)
    assert promedios[0] == 700       # lunes
    assert promedios[5] == 100       # sábado
    assert promedios[2] == 0         # miércoles sin ventas


def _flujo(**cambios):
    parametros = dict(
        hoy=LUNES, semanas=2, saldo_inicial=1000, promedios=[100] * 7, factores_mes={},
        escenario_pct=100, facturas=[], gastos=[], liquidaciones=[], tasa_comision_bp=0,
    )
    parametros.update(cambios)
    return flujo_semanal(**parametros)


def test_flujo_acumula_saldo_y_carga_lo_vencido_a_la_semana_actual():
    vencida = SimpleNamespace(saldo=500, fecha_limite=date(2026, 9, 1))
    arriendo = SimpleNamespace(frecuencia="mensual", dia=5, valor=300)   # 5/10 = lunes de la semana 2
    s1, s2 = _flujo(facturas=[vencida], gastos=[arriendo])

    assert s1["ventas"] == 700 and s1["facturas"] == 500
    assert s1["saldo_final"] == 1200
    assert s2["gastos"] == 300
    assert s2["saldo_inicial"] == 1200 and s2["saldo_final"] == 1600


def test_factor_de_temporada_y_escenario():
    s1, _ = _flujo(factores_mes={10: 200}, escenario_pct=50)
    # 28-30 sep: 3 días × 100 × 50% = 150 | 1-4 oct: 4 días × 100 × 200% × 50% = 400
    assert s1["ventas"] == 550