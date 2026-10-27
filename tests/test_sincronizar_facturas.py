import os
from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models import Venta, Cliente, Vendedora
from app.services.sincronizar_facturas import planear, aplicar
from config import Config


class ConfigSync(Config):
    TESTING = True
    DB_NAME = "pytest-sincronizar.db"


@pytest.fixture
def app():
    app = create_app(ConfigSync)
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(Vendedora(nombre="Patricia", tasa_comision_bp=200))
        db.session.commit()
        yield app
        db.session.remove()
        db.engine.dispose()
    os.remove(app.config["DB_PATH"])


def _venta(numero, descripcion=None, cliente="Ana Ruiz", telefono="3001234567", red="TikTok"):
    return {"numero": numero, "fecha": date(2026, 10, 16), "canal": "Minorista", "vendedora": "Patricia",
            "cliente": cliente, "telefono": telefono, "medio_contacto": red, "valor": 150000, "prendas": 1,
            "pagos": {"Efectivo": 150000},
            "lineas": [{"referencia": "05123", "descripcion": descripcion, "cantidad": 1,
                        "precio_unitario": 150000, "color": None}]}


def test_crea_actualiza_y_no_duplica(app):
    aplicar(planear([_venta(1), _venta(2, cliente="Ana", telefono=None)], []))
    assert Venta.query.count() == 2 and Cliente.query.count() == 2
    assert all(c.autoriza_datos and c.fecha_autorizacion for c in Cliente.query)   # se pidió en la factura

    # Mismo Excel con la descripción completada: se actualiza, no se crea nada nuevo
    plan = planear([_venta(1, "Vestido Corto"), _venta(2, cliente="Ana", telefono=None)], [])
    assert plan["nuevas"] == [] and [c for _, _, c in plan["actualizar"]] == [["prendas"]]
    aplicar(plan)
    assert Venta.query.filter_by(numero_factura=1).one().lineas[0].descripcion == "Vestido Corto"
    assert Venta.query.count() == 2 and Cliente.query.count() == 2      # la clienta sin celular no se duplicó

    plan = planear([_venta(1, "Vestido Corto"), _venta(2, cliente="Ana", telefono=None)], [])
    assert plan["iguales"] == 2 and not plan["actualizar"]


def test_mismo_celular_es_el_mismo_cliente(app):
    aplicar(planear([_venta(1, cliente="Xiomara"), _venta(2, cliente="Nancy")], []))
    assert Cliente.query.count() == 1
    assert planear([_venta(1, cliente="Xiomara"), _venta(2, cliente="Nancy")], [])["iguales"] == 2
