import json

from app.services.detalle_venta import leer_detalle


def _detalle(*prendas):
    """Arma el JSON igual que lo arma el formulario."""
    return json.dumps(list(prendas))


def test_sin_detalle_no_es_error():
    assert leer_detalle("", 3) == ([], None)
    assert leer_detalle("[]", 3) == ([], None)


def test_detalle_valido_y_normalizado():
    lineas, error = leer_detalle(_detalle(
        {"referencia": "05700", "color": " NEGRO ", "talla": "m", "cantidad": "2", "precio": "140.000"},
        {"referencia": "2313", "cantidad": 1, "precio": 200000},
    ), 3)

    assert error is None
    assert lineas[0] == {"referencia": "5700", "cantidad": 2, "precio_unitario": 140000,
                         "color": "Negro", "talla": "M"}
    assert lineas[1]["color"] is None and lineas[1]["talla"] is None   # color y talla son opcionales


def test_la_suma_debe_cuadrar_exacto():
    _, error = leer_detalle(_detalle({"referencia": "5700", "cantidad": 2, "precio": 1000}), 3)
    assert error == "el detalle suma 2 prendas, pero la venta dice 3."


def test_prenda_sin_precio_y_json_danado():
    _, error = leer_detalle(_detalle({"referencia": "5700", "cantidad": 1, "precio": ""}), 1)
    assert "prenda 1" in error

    _, error = leer_detalle("{esto no es json", 1)
    assert error == "el detalle de prendas llegó dañado."