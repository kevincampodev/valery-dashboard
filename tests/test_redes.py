from datetime import date

from app.services.redes import periodo_comparable, resumen_por_red, por_dia_semana, clientes_nuevos, variacion


def test_mes_en_curso_se_compara_con_los_mismos_dias():
    assert periodo_comparable(date(2026, 10, 1), date(2026, 10, 31), date(2026, 10, 24)) == (
        date(2026, 9, 1), date(2026, 9, 24))
    # mes cerrado: contra el mes anterior completo
    assert periodo_comparable(date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 24)) == (
        date(2026, 8, 1), date(2026, 8, 31))
    # 31 de marzo contra febrero (que solo tiene 28)
    assert periodo_comparable(date(2026, 3, 1), date(2026, 3, 31), date(2026, 3, 31))[1] == date(2026, 2, 28)


def test_resumen_por_red():
    r = resumen_por_red([("TikTok", 100), ("TikTok", 200), ("Facebook", 50)], [("TikTok", 200)])
    assert r["TikTok"] == {"total": 300, "numero": 2, "promedio": 150, "anterior": 200,
                           "variacion": 50, "variacion_numero": 100}
    assert r["Facebook"]["variacion"] is None                 # antes no había ventas
    assert r["Total"]["total"] == 350 and r["Total"]["numero"] == 3
    assert variacion(50, 100) == -50


def test_dia_de_la_semana_y_clientes():
    semana = por_dia_semana([(date(2026, 10, 24), "Instagram", 80)])    # sábado
    assert semana["Instagram"][5] == 80
    conteo = clientes_nuevos([(1, "TikTok"), (1, "TikTok"), (2, "TikTok"), (None, "TikTok")],
                             {1: date(2026, 10, 3), 2: date(2026, 5, 1)}, date(2026, 10, 1))
    assert conteo["TikTok"] == {"nuevos": 1, "repiten": 1, "sin_dato": 1}
