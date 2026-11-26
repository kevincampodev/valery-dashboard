import os
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models import Usuario, Venta, Vendedora, Meta, PagoVenta
from config import Config


class ConfigTablero(Config):
    TESTING = True
    DB_NAME = "pytest-tablero.db"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def cliente():
    app = create_app(ConfigTablero)
    with app.app_context():
        db.drop_all()
        db.create_all()
        u = Usuario(usuario="alejo", nombre="Alejo", rol="superadmin", totp_activo=True, debe_cambiar_password=False)
        u.fijar_password("clave-de-prueba-123")
        ana = Vendedora(nombre="Ana", tasa_comision_bp=200)
        db.session.add_all([u, ana, Meta(periodo=date(2026, 11, 1), canal="Total", valor=1_000_000)])
        mixta = Venta(fecha=date(2026, 11, 3), canal="Minorista", medio_pago="Mixto", valor=150_000, vendedora=ana)
        mixta.pagos = [PagoVenta(medio="Efectivo", valor=100_000), PagoVenta(medio="Nequi", valor=50_000)]
        db.session.add_all([mixta, Venta(fecha=date(2026, 10, 2), canal="Mayorista", medio_pago="Efectivo", valor=90_000)])
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


def test_tablero_del_mes(cliente):
    pagina = cliente.get("/ventas/?mes=2026-11").get_data(as_text=True)
    assert "Meta del mes" in pagina and "Acumulado del mes" in pagina and "Calendario" in pagina
    assert "Nequi" in pagina                      # el pago mixto se reparte entre sus medios
    assert cliente.get("/ventas/?mes=2025-01").status_code == 200   # un mes sin ventas no se rompe
