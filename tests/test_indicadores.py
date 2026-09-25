from datetime import date
from types import SimpleNamespace

from app.services.indicadores import resumen_deudas, deuda_por_proveedor, vencimientos_por_semana

HOY = date(2026, 9, 24)  # jueves; la semana arranca el lunes 21/09


def factura(saldo, fecha, estado="al día", proveedor="X"):
    return SimpleNamespace(saldo=saldo, fecha_limite=fecha, estado=estado,
                           proveedor=SimpleNamespace(nombre=proveedor))


def test_vencimientos_por_semana():
    facturas = [
        factura(100, date(2026, 9, 22)),   # ya vencida
        factura(50, date(2026, 9, 24)),    # vence hoy -> semana actual
        factura(30, date(2026, 9, 28)),    # lunes siguiente -> semana 2
        factura(20, date(2026, 12, 31)),   # más allá del horizonte
        factura(0, date(2026, 9, 25)),     # pagada: no cuenta
    ]
    etiquetas, valores = vencimientos_por_semana(facturas, HOY)

    assert len(etiquetas) == 10
    assert etiquetas[0] == "Vencido" and etiquetas[1] == "21/09" and etiquetas[-1] == "Después"
    assert valores[0] == 100
    assert valores[1] == 50
    assert valores[2] == 30
    assert valores[-1] == 20
    assert sum(valores) == 200


def test_resumen_ordena_urgentes_por_fecha():
    a = factura(100, date(2026, 9, 30), estado="por vencer")
    b = factura(200, date(2026, 5, 1), estado="vencida")
    c = factura(300, date(2026, 12, 1), estado="al día")
    r = resumen_deudas([a, b, c])

    assert r["deuda_total"] == 600
    assert r["vencido"] == 200 and r["n_vencidas"] == 1
    assert r["por_vencer"] == 100
    assert r["urgentes"] == [b, a]


def test_deuda_por_proveedor_de_mayor_a_menor():
    facturas = [factura(10, HOY, proveedor="A"), factura(50, HOY, proveedor="B"),
                factura(15, HOY, proveedor="A")]
    assert deuda_por_proveedor(facturas) == [("B", 50), ("A", 25)]