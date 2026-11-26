import os
from datetime import date, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Usuario, Proveedor, Factura, Cliente, Venta
from config import Config


class ConfigMenu(Config):
    TESTING = True
    DB_NAME = "pytest-menu.db"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    app = create_app(ConfigMenu)
    with app.app_context():
        db.drop_all()
        db.create_all()
        for usuario, rol in (("alejo", "superadmin"), ("jose", "marketing")):
            u = Usuario(usuario=usuario, nombre=usuario.capitalize(), rol=rol, totp_activo=True, debe_cambiar_password=False)
            u.fijar_password("clave-de-prueba-123")
            db.session.add(u)
        hoy = date.today()
        texika = Proveedor(nombre="Texika SAS")
        cliente = Cliente(nombre="Marly Vannesa", telefono="3001234567")
        db.session.add_all([texika, cliente])
        db.session.flush()
        db.session.add_all([
            Factura(proveedor_id=texika.id, numero="TX3882", fecha_emision=hoy - timedelta(days=90),
                    fecha_vencimiento=hoy - timedelta(days=10), total=1_000_000),
            Venta(fecha=hoy - timedelta(days=80), canal="Mayorista", medio_pago="Efectivo", valor=900_000,
                  cliente=cliente, numero_factura=625),
        ])
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    os.remove(app.config["DB_PATH"])


def entrar(app, usuario):
    with app.app_context():
        uid = Usuario.query.filter_by(usuario=usuario).first().get_id()
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = uid
        s["_fresh"] = True
    return c


def test_admin_ve_todo_con_contadores(app):
    c = entrar(app, "alejo")
    pagina = c.get("/aplicaciones").get_data(as_text=True)
    for nombre in ("Ventas diarias", "Pagos pendientes", "Resumen de redes", "Sistema"):
        assert nombre in pagina
    assert "1 factura vencida" in pagina                       # contador de Pagos pendientes
    assert "1 cliente sin volver" in pagina                      # contador de Clientes
    menu = c.get("/deudas/").get_data(as_text=True)
    assert 'class="menu-grupo contiene-activo" data-grupo="Proveedores"' in menu   # su sección queda abierta


def test_buscador(app):
    c = entrar(app, "alejo")
    assert c.get("/buscar?q=texi").get_json()["resultados"][0]["titulo"] == "Texika SAS"
    assert c.get("/buscar?q=TX38").get_json()["resultados"][0]["grupo"] == "Facturas de proveedores"
    assert c.get("/buscar?q=%23625").get_json()["resultados"][0]["titulo"] == "Factura #625"
    marly = c.get("/buscar?q=1234567").get_json()["resultados"][0]
    assert marly["titulo"] == "Marly Vannesa" and "300" in marly["detalle"]
    assert c.get("/buscar?q=x").get_json()["resultados"] == []    # mínimo 2 letras


def test_marketing_solo_ve_lo_suyo(app):
    c = entrar(app, "jose")
    pagina = c.get("/aplicaciones").get_data(as_text=True)
    assert "Resumen de redes" in pagina and "Publicidad" in pagina
    for oculto in ("Pagos pendientes", "Deudas", "Ventas diarias", "Registrar ventas", "Sistema"):
        assert oculto not in pagina
    assert c.get("/buscar?q=texi").get_json()["resultados"] == []  # ni clientes ni proveedores
    assert c.get("/deudas/").status_code == 403
