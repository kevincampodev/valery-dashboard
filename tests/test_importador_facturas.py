from datetime import date, datetime

from openpyxl import Workbook

from app.services.importador_facturas import (leer_facturas, leer_fecha, normalizar_vendedora,
                                              numeros_faltantes, VENDEDORA_MAYORISTA)

ENCABEZADO = ["# factura", "fecha", "nombre cliente", "# telefono", "ref", "descripcion", "cantidad", "color",
              "valor unitario", "Subtotal", "valor total factura", "metodo de pago", "Valor metodo de pago",
              "Valor pagado", "Valor que debe", "vendedora", "de donde viene?"]
D = datetime(2026, 10, 1)


def _archivo(tmp_path, filas):
    wb = Workbook()
    ws = wb.active
    ws.append(ENCABEZADO)
    for fila in filas:
        ws.append(list(fila) + [None] * (17 - len(fila)))
    ruta = tmp_path / "facturas.xlsx"
    wb.save(ruta)
    return ruta


def test_factura_de_varias_filas_con_pago_mixto_y_saldo(tmp_path):
    ruta = _archivo(tmp_path, [
        (1, D, "marly vannesa", 3207471715, "09196", "Conjunto", 1, "negro", 110000, 110000, 220000,
         "Bancolombia", 130000, 200000, 20000, "Melany", "Voz a voz"),
        (None, None, None, None, "Zapatos", "(par)", 1, "Blanco", 110000, 110000, None, "Efectivo", 70000),
    ])
    ventas, abonos, avisos = leer_facturas(ruta)

    assert abonos == [] and len(ventas) == 1
    v = ventas[0]
    assert v["valor"] == 220000 and v["prendas"] == 2 and v["cliente"] == "Marly Vannesa"
    assert v["pagos"] == {"Bancolombia": 150000, "Efectivo": 70000}      # lo que debía se marca pagado
    assert v["lineas"][0]["referencia"] == "09196" and v["lineas"][0]["color"] == "Negro"
    assert v["canal"] == "Minorista" and v["medio_contacto"] == "Voz a voz"
    assert any("debía 20000" in a for a in avisos)


def test_abono_mayorista_y_filas_de_solo_pago(tmp_path):
    ruta = _archivo(tmp_path, [
        (2, D, None, None, "ABONO SALDO", "ABONO SALDO", None, None, 80000, 80000, 80000, "Bold Datafono", 80000),
        (4, D, "Jaqueline", "3168849557", "09002", "Conjunto", 6, None, 85000, 510000, 510000, "Efectivo", 400000,
         None, None, "AL X MAYOR"),
        (None, None, None, None, None, None, None, None, None, None, None, "Nequi", 110000),
    ])
    ventas, abonos, _ = leer_facturas(ruta)

    assert abonos == [{"numero": 2, "fecha": date(2026, 10, 1), "valor": 80000, "medio": "Bold Datáfono",
                       "cliente": None}]
    assert ventas[0]["canal"] == "Mayorista" and ventas[0]["vendedora"] == VENDEDORA_MAYORISTA
    assert len(ventas[0]["lineas"]) == 1 and ventas[0]["pagos"] == {"Efectivo": 400000, "Nequi": 110000}
    assert numeros_faltantes(ventas, abonos) == [3]


def test_normalizaciones():
    assert leer_fecha("03/10/226") == date(2026, 10, 3)
    assert leer_fecha("basura") is None
    assert normalizar_vendedora("andrea") == "Andrea"
    assert normalizar_vendedora(None) is None
