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