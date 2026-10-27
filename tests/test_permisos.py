import os
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models import Usuario, Venta, Cliente
from config import Config


class ConfigPermisos(Config):
    TESTING = True
    DB_NAME = "pytest-permisos.db"     # base temporal, se borra al terminar
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


@pytest.fixture
def app():
    app = create_app(ConfigPermisos)
    with app.app_context():
        db.drop_all()
        db.create_all()
        for usuario, rol in (("alejo", "superadmin"), ("brayan", "admin"), ("jose", "marketing")):
            u = Usuario(usuario=usuario, nombre=usuario.title(), rol=rol, totp_activo=True,
                        debe_cambiar_password=False)
            u.fijar_password("clave-de-prueba-123")
            db.session.add(u)
        cliente = Cliente(nombre="Clienta Secreta", telefono="3001234567")
        db.session.add(Venta(fecha=date.today(), canal="Minorista", medio_pago="Efectivo", valor=150000,
                             medio_contacto="TikTok", numero_factura=77, cliente=cliente))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    os.remove(app.config["DB_PATH"])


def _entrar(app, usuario):
    cliente = app.test_client()
    with app.app_context():
        uid = Usuario.query.filter_by(usuario=usuario).one().get_id()
    with cliente.session_transaction() as s:
        s["_user_id"] = uid
        s["_fresh"] = True
    return cliente


def test_marketing_solo_ve_redes(app):
    c = _entrar(app, "jose")
    assert c.get("/").headers["Location"].endswith("/redes/")      # su inicio es el resumen de redes
    for url in ("/redes/", "/redes/facturas", "/redes/facturas/excel", "/publicidad/", "/cuenta"):
        assert c.get(url).status_code == 200, url
    for url in ("/deudas/", "/ventas/", "/mayoristas/", "/clientes/", "/comisiones/", "/sistema/", "/sistema/bitacora"):
        assert c.get(url).status_code == 403, url


def test_marketing_no_puede_guardar_ni_ver_margenes(app):
    c = _entrar(app, "jose")
    assert c.post("/publicidad/margen", data={"margen": "90"}).status_code == 403
    assert c.post("/publicidad/pauta", data={"plataforma": "TikTok", "desde": "2026-10",
                                            "valor_diario": "1"}).status_code == 403
    pagina = c.get("/publicidad/").get_data(as_text=True)
    for privado in ("Margen de ganancia", "Comisiones", "Resultado acumulado", "ganancia", "Registrar pauta", "% del mes"):
        assert privado not in pagina


def test_facturas_por_redes_sin_datos_del_cliente(app):
    pagina = _entrar(app, "jose").get("/redes/facturas").get_data(as_text=True)
    assert "77" in pagina and "TikTok" in pagina and "$150.000" in pagina
    assert "Clienta Secreta" not in pagina and "300" not in pagina


def test_vista_previa_solo_para_super_administrador(app):
    assert _entrar(app, "brayan").post("/cuenta/vista-previa", data={"rol": "marketing"}).status_code == 403

    c = _entrar(app, "alejo")
    assert c.get("/deudas/").status_code == 200
    c.post("/cuenta/vista-previa", data={"rol": "marketing"})
    assert c.get("/deudas/").status_code == 403                    # ve lo mismo que marketing
    assert c.get("/redes/").status_code == 200
    assert c.post("/cuenta/perfil", data={"nombre": "Otro"}).status_code == 403   # nada se guarda
    c.post("/cuenta/vista-previa/salir")
    assert c.get("/deudas/").status_code == 200
