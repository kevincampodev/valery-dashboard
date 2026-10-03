from datetime import date
from types import SimpleNamespace

from app.services.mayoristas import normalizar_referencia, leer_lineas, total_lineas, historial_precios, es_mayorista


def test_regla_mayorista():
    assert es_mayorista(True, 700_001, 700_000)
    assert not es_mayorista(True, 700_000, 700_000)       # "cuando pase" de 700 mil: exactamente 700 mil es minorista
    assert not es_mayorista(False, 5_000_000, 700_000)    # sin permiso mayorista nunca es mayorista


def test_normalizar_referencia():
    assert normalizar_referencia("09176") == "09176"
    assert normalizar_referencia("5085") == "05085"          # completa a 5 dígitos
    assert normalizar_referencia("  vestido   largo ") == "VESTIDO LARGO"
    assert normalizar_referencia(None) == ""


def test_leer_lineas_ignora_vacias_y_reporta_incompletas():
    lineas, errores = leer_lineas(["09200", "", "7105", "5085"],
                                  ["12", "", "", "3"],
                                  ["85.000", "", "90000", "70000"])
    assert lineas == [{"referencia": "09200", "cantidad": 12, "precio_unitario": 85000},
                      {"referencia": "05085", "cantidad": 3, "precio_unitario": 70000}]
    assert errores == ["Línea 3: referencia, cantidad y precio unitario son obligatorios."]
    assert total_lineas(lineas) == 1_230_000


def _registro(dia, ref, cantidad, precio, cliente="A"):
    return SimpleNamespace(fecha=date(2026, 9, dia), referencia=ref, cantidad=cantidad,
                           precio_unitario=precio, cliente=cliente)


def test_historial_precios_promedio_ponderado_y_ultimo():
    h = historial_precios([_registro(20, "9200", 10, 80000, "B"),
                           _registro(5, "9200", 2, 95000),
                           _registro(10, "5085", 1, 70000)])
    assert list(h) == ["5085", "9200"]
    r = h["9200"]
    assert r["ultimo"] == 80000 and r["cliente_ultimo"] == "B"
    assert r["promedio"] == 82500
    assert (r["minimo"], r["maximo"], r["unidades"]) == (80000, 95000, 12)