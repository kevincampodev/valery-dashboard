from datetime import date

from app.services.indicadores import clientes_sin_comprar


def test_clientes_sin_comprar_ordena_del_mas_olvidado():
    hoy = date(2026, 9, 30)
    clientes = [
        ("A", date(2026, 9, 20), 1_000_000),   # 10 días: todavía está activo
        ("B", date(2026, 7, 1), 5_000_000),    # 91 días
        ("C", date(2026, 8, 1), 2_000_000),    # 60 días
        ("D", None, 0),                        # nunca ha comprado: no cuenta
    ]
    frios = clientes_sin_comprar(clientes, hoy, dias=45)

    assert [f["cliente"] for f in frios] == ["B", "C"]
    assert frios[0]["dias"] == 91