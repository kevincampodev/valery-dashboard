import os
from datetime import date, timedelta
from types import SimpleNamespace as N
from urllib.parse import unquote

import pytest

from app import create_app
from app.extensions import db
from app.models import Usuario, Venta, Cliente
from app.services.inicio import saludo, proximos_pagos, deuda_proveedores, enlace_whatsapp, clientes_para_recuperar
from config import Config

HOY = date(2026, 11, 25)


def factura(id, proveedor, saldo, dias):
    return N(id=id, proveedor_id=proveedor, proveedor=N(nombre=f"Prov {proveedor}"), saldo=saldo,
             fecha_limite=HOY + timedelta(days=dias))


def test_saludo():
    assert saludo(8) == "Buenos días" and saludo(15) == "Buenas tardes" and saludo(20) == "Buenas noches"


def test_agenda_de_pagos():
    facturas = [factura(1, 1, 100, 10), factura(2, 1, 200, -5), factura(3, 2, 300, 3),
                factura(4, 2, 0, -1), factura(5, 3, 400, 60)]
    filas, n, total = proximos_pagos(facturas, HOY)
    assert [f["factura"].id for f in filas] == [2, 3, 1]          # vencida primero; pagada y lejana fuera
    assert [f["urgencia"] for f in filas] == ["vencida", "pronto", "normal"]
    assert n == 3 and total == 600 and filas[0]["mes"] == "nov"


def test_deuda_por_proveedor():
    filas = deuda_proveedores([factura(1, 1, 100, 1), factura(2, 2, 300, 1), factura(3, 2, 0, 1)])
    assert [(f["id"], f["valor"], f["numero"], f["porcentaje"]) for f in filas] == [(2, 300, 1, 75), (1, 100, 1, 25)]


def test_enlace_whatsapp():
    url = enlace_whatsapp("300 123 4567", "MARLY vannesa")
    assert url.startswith("https://wa.me/573001234567?text=") and "Hola Marly," in unquote(url)
    assert "Hola," in unquote(enlace_whatsapp("573001234567", "Cliente 300 123 4567"))
    assert enlace_whatsapp("6021234567", "Fijo") is None and enlace_whatsapp(None, "x") is None


def test_clientes_para_recuperar():
    a, b, c = (N(nombre=n, telefono="3001234567") for n in ("A", "B", "C"))
    compras = [(a, HOY - timedelta(days=50), 100), (b, HOY - timedelta(days=90), 900), (c, HOY - timedelta(days=10), 5000)]
    filas, n = clientes_para_recuperar(compras, HOY, dias=45)
    assert n == 2 and [f["cliente"].nombre for f in filas] == ["B", "A"]    # el que más compraba primero


class ConfigInicio(Config):
    TESTING = True
    DB_NAME = "pytest-inicio.db"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def cliente():
    app = create_app(ConfigInicio)
    with app.app_context():
        db.drop_all()
        db.create_all()
        u = Usuario(usuario="alejo", nombre="Kevin Campo", rol="superadmin", totp_activo=True, debe_cambiar_password=False)
        u.fijar_password("clave-de-prueba-123")
        cli = Cliente(nombre="Marly Vannesa", telefono="3001234567", es_mayorista=True)
        hoy = date.today()
        db.session.add_all([u, cli,
                            Venta(fecha=hoy.replace(day=1), canal="Minorista", medio_pago="Efectivo", valor=150_000),
                            Venta(fecha=hoy - timedelta(days=80), canal="Mayorista", medio_pago="Efectivo",
                                  valor=900_000, cliente=cli, medio_contacto="WhatsApp")])
        db.session.commit()
        uid = u.get_id()
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = uid
        s["_fresh"] = True
    yield c
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    os.remove(app.config["DB_PATH"])


def test_pagina_de_inicio(cliente):
    pagina = cliente.get("/").get_data(as_text=True)
    assert ", Kevin" in pagina and "Meta de" in pagina and "Próximos pagos" in pagina
    assert "no tiene meta" in pagina and "Definir" in pagina           # alerta de meta sin definir
    assert "Marly Vannesa" in pagina and "wa.me/573001234567" in pagina  # cliente para recuperar con WhatsApp
