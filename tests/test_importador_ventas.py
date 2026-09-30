from datetime import date, datetime

import pytest
from openpyxl import Workbook

from app.services.importador_ventas import leer_revision, resumir


def _archivo(tmp_path, filas, hoja="Ventas"):
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    ws.append(["FILA ORIGINAL", "FECHA", "CLIENTE", "VENDEDOR", "VALOR", "MEDIO DE CONTACTO", "CANAL"])
    for fila in filas:
        ws.append(fila)
    ruta = tmp_path / "revision.xlsx"
    wb.save(ruta)
    return ruta


def test_lee_normaliza_y_omite(tmp_path):
    ruta = _archivo(tmp_path, [
        (10, datetime(2026, 9, 1), "Ana", " patricia ", 150000, "TIK TOK", "Minorista"),
        (11, "15/09/2026", "Luis", "Ruby", 2000000, "ORGANICO", "Mayorista"),
        (12, datetime(2026, 9, 2), "Eva", "Ruby", 90000, "VOZ A VOZ", "REVISAR"),
        (13, None, "Monica", "Patricia", 190000, "ORGANICO", "Minorista"),
        (14, datetime(2026, 9, 3), "Sol", "", None, "ORGANICO", "Minorista"),
    ])
    ventas, omitidas = leer_revision(ruta)

    assert len(ventas) == 3
    assert ventas[0]["vendedora"] == "Patricia" and ventas[0]["medio_contacto"] == "TikTok"
    assert ventas[1]["fecha"] == date(2026, 9, 15) and ventas[1]["canal"] == "Mayorista"
    assert ventas[2]["canal"] == "Minorista"                  # REVISAR se asume minorista
    assert omitidas == [(13, "fecha inválida"), (14, "sin valor")]
    assert resumir(ventas)["Por canal"] == {"Mayorista": 2000000, "Minorista": 240000}


def test_archivo_sin_hoja_ventas(tmp_path):
    with pytest.raises(ValueError, match="Ventas"):
        leer_revision(_archivo(tmp_path, [], hoja="Otra"))