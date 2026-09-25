from datetime import date
from types import SimpleNamespace

from app.services.ventas import resumen_mes


def venta(dia, canal, valor, devolucion=False, vendedora=None, medio="Efectivo"):
    return SimpleNamespace(
        fecha=date(2026, 9, dia), canal=canal, valor=valor, es_devolucion=devolucion,
        neto=-valor if devolucion else valor, medio_pago=medio,
        vendedora=SimpleNamespace(nombre=vendedora) if vendedora else None,
    )


def test_resumen_mes_con_devolucion():
    registros = [
        venta(1, "Minorista", 100, vendedora="Ana"),
        venta(1, "Mayorista", 300),
        venta(2, "Minorista", 50, devolucion=True, vendedora="Ana"),
        venta(3, "Minorista", 200, vendedora="Luz", medio="Transferencia"),
    ]
    r = resumen_mes(registros, date(2026, 9, 1), date(2026, 9, 30))

    assert len(r["por_dia"]) == 30                      # incluye los días vacíos
    assert r["total"] == 550                            # 100 + 300 - 50 + 200
    assert r["devoluciones"] == 50
    assert r["por_canal"] == {"Minorista": 250, "Mayorista": 300}
    assert r["por_dia"][date(2026, 9, 2)]["neto"] == -50
    assert r["dias_registrados"] == 3
    assert r["promedio_diario"] == 183                  # 550 // 3
    assert list(r["por_vendedora"].items()) == [("Sin vendedora", 300), ("Luz", 200), ("Ana", 50)]


def test_mes_sin_ventas():
    r = resumen_mes([], date(2026, 2, 1), date(2026, 2, 28))
    assert r["total"] == 0
    assert r["promedio_diario"] == 0   # sin división por cero
    assert len(r["por_dia"]) == 28