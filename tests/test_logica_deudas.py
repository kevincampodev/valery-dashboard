from datetime import date
from types import SimpleNamespace

from app.services.abonos import distribuir_fifo
from app.services.cartera import rango_edad


def factura(numero, saldo, dia):
    return SimpleNamespace(numero=numero, saldo=saldo, fecha_limite=date(2026, 9, dia))


def test_fifo_paga_primero_la_mas_antigua():
    a, b, c = factura("A", 100, 20), factura("B", 50, 5), factura("C", 80, 10)
    plan, sobrante = distribuir_fifo([a, b, c], 140)
    assert [(f.numero, m) for f, m in plan] == [("B", 50), ("C", 80), ("A", 10)]
    assert sobrante == 0


def test_fifo_deja_sobrante_si_paga_de_mas():
    plan, sobrante = distribuir_fifo([factura("A", 100, 1)], 150)
    assert plan[0][1] == 100
    assert sobrante == 50


def test_fifo_ignora_facturas_pagadas():
    plan, _ = distribuir_fifo([factura("A", 0, 1), factura("B", 30, 2)], 30)
    assert [f.numero for f, _ in plan] == ["B"]


def test_rangos_de_edad_en_los_limites():
    assert rango_edad(0) == "Al día"
    assert rango_edad(-1) == "1-30"
    assert rango_edad(-30) == "1-30"
    assert rango_edad(-31) == "31-60"
    assert rango_edad(-90) == "61-90"
    assert rango_edad(-91) == "+90"