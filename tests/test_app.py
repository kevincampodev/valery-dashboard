from app import create_app
from config import Config


class ConfigPrueba(Config):
    TESTING = True
    DB_NAME = "pytest.db"          # nunca la base real
    WTF_CSRF_ENABLED = False


def test_la_app_arranca_y_registra_todos_los_modulos():
    app = create_app(ConfigPrueba)
    endpoints = {regla.endpoint for regla in app.url_map.iter_rules()}

    for modulo in ("dashboard", "deudas", "abonos", "ventas", "mayoristas", "metas", "comisiones", "proyecciones",
                   "pagos", "marketing", "documentos", "reportes", "sistema"):
        assert f"{modulo}.index" in endpoints, f"El módulo {modulo} no quedó registrado"


def test_sin_sesion_todo_redirige_al_login():
    cliente = create_app(ConfigPrueba).test_client()

    respuesta = cliente.get("/deudas/")
    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]

    assert cliente.get("/login").status_code == 200          # el login sí es público


def test_encabezados_de_seguridad():
    respuesta = create_app(ConfigPrueba).test_client().get("/login")
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in respuesta.headers["Content-Security-Policy"]
    assert respuesta.headers["Cache-Control"] == "no-store"