import io
import os
from datetime import date, timedelta
from types import SimpleNamespace as N

import pytest
from openpyxl import load_workbook

from app import create_app
from app.extensions import db
from app.models import Usuario, Proveedor, Factura, Pago, AplicacionPago
from app.services.deudas_vista import (fila, en_pestana, filtrar, ordenar, resumen, totales, por_proveedor,
                                       meses_disponibles)
from config import Config

HOY = date(2026, 11, 25)


def factura(id, prov, total, dias, abonos=(), contado=False, pactada=None, etiqueta=None, emision=date(2026, 9, 1)):
    aplicaciones = [N(valor=v, pago=N(fecha=HOY + timedelta(days=d))) for v, d in abonos]
    abonado = sum(v for v, _ in abonos)
    limite = HOY + timedelta(days=dias)
    return N(id=id, proveedor_id=prov, proveedor=N(nombre=f"Proveedor {prov}"), numero=f"F{id}", etiqueta=etiqueta,
             fecha_emision=emision, fecha_vencimiento=limite if not pactada else limite - timedelta(days=pactada),
             fecha_pactada=limite if pactada else None, fecha_limite=limite, total=total, abonado=abonado,
             saldo=0 if contado else total - abonado, pagada_contado=contado, aplicaciones=aplicaciones)


FACTURAS = [
    factura(1, 1, 1000, -10, abonos=[(400, -20)]),                 # vencida, abonada 40%
    factura(2, 1, 500, 3),                                          # vence esta semana
    factura(3, 2, 800, 30, pactada=15, etiqueta="Temporada"),       # al día, con fecha pactada
    factura(4, 2, 300, -40, abonos=[(100, -50), (200, -35)]),       # pagada 5 días tarde en 2 abonos
    factura(5, 3, 700, -60, contado=True, emision=date(2026, 8, 5)),  # de contado
]


def test_cada_fila_es_exacta():
    a, b, c, d, e = (fila(f, HOY) for f in FACTURAS)
    assert (a["estado"], a["saldo"], a["abonado"], a["porcentaje"], a["dias"]) == ("vencida", 600, 400, 40, -10)
    assert b["estado"] == "por vencer" and c["estado"] == "al día"
    assert c["original"] == HOY + timedelta(days=15)                # se muestra la fecha original de la factura
    assert (d["estado"], d["fecha_pago"], d["retraso"], d["n_abonos"]) == ("pagada", HOY - timedelta(days=35), 5, 2)
    assert (e["estado"], e["abonado"], e["fecha_pago"]) == ("pagada", 700, date(2026, 8, 5))


def test_pestanas_filtros_y_orden():
    filas = [fila(f, HOY) for f in FACTURAS]
    assert [x["id"] for x in ordenar(en_pestana(filas, "pendientes"))] == [1, 2, 3]   # lo más urgente arriba
    assert [x["id"] for x in en_pestana(filas, "vencidas")] == [1]
    assert [x["id"] for x in ordenar(en_pestana(filas, "pagadas"))] == [4, 5]        # lo pagado más reciente arriba
    assert [x["id"] for x in filtrar(filas, texto="temporáda")] == [3]                # sin importar tildes
    assert [x["id"] for x in filtrar(filas, proveedor_id=2)] == [3, 4]
    assert [x["id"] for x in filtrar(filas, mes="2026-08")] == [5]
    assert meses_disponibles(filas) == ["2026-09", "2026-08"]


def test_resumen_totales_y_proveedores():
    filas = [fila(f, HOY) for f in FACTURAS]
    r = resumen(filas)
    assert (r["deuda"], r["numero"], r["proveedores"]) == (1900, 3, 2)
    assert [(t["estado"], t["valor"]) for t in r["tramos"]] == [("vencida", 600), ("por vencer", 500), ("al día", 800)]
    assert totales(filas) == {"total": 3300, "abonado": 1400, "saldo": 1900, "numero": 5}
    grupos = por_proveedor(filas)
    assert [(g["id"], g["saldo"], g["pendientes"], g["mas_vencida"], g["estado"]) for g in grupos] == [
        (1, 1100, 2, -10, "vencida"), (2, 800, 1, 30, "al día"), (3, 0, 0, None, "pagada")]


class ConfigDeudas(Config):
    TESTING = True
    DB_NAME = "pytest-deudas.db"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def cliente():
    app = create_app(ConfigDeudas)
    with app.app_context():
        db.drop_all()
        db.create_all()
        u = Usuario(usuario="alejo", nombre="Alejo", rol="superadmin", totp_activo=True, debe_cambiar_password=False)
        u.fijar_password("clave-de-prueba-123")
        texika, nikotex = Proveedor(nombre="Texika SAS"), Proveedor(nombre="NIKOTEX")
        db.session.add_all([u, texika, nikotex])
        db.session.flush()
        hoy = date.today()
        vencida = Factura(proveedor_id=texika.id, numero="TX3882", fecha_emision=hoy - timedelta(days=90),
                          fecha_vencimiento=hoy - timedelta(days=10), total=1_000_000)
        pagada = Factura(proveedor_id=nikotex.id, numero="NK46", fecha_emision=hoy - timedelta(days=60),
                         fecha_vencimiento=hoy - timedelta(days=30), total=500_000)
        db.session.add_all([vencida, pagada])
        db.session.flush()
        pago = Pago(proveedor_id=nikotex.id, fecha=hoy - timedelta(days=20), valor=500_000, medio="Transferencia")
        pago.aplicaciones = [AplicacionPago(factura_id=pagada.id, valor=500_000)]
        db.session.add(pago)
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


def test_pagina_de_deudas(cliente):
    pendientes = cliente.get("/deudas/").get_data(as_text=True)
    assert "Debes en total" in pendientes and "TX3882" in pendientes and "NK46" not in pendientes
    pagadas = cliente.get("/deudas/?ver=pagadas").get_data(as_text=True)
    assert "NK46" in pagadas and "Pagada 10 días tarde" in pagadas
    assert "TX3882" in cliente.get("/deudas/?estado=vencida").get_data(as_text=True)     # enlaces del Inicio
    agrupado = cliente.get("/deudas/?vista=proveedores&ver=todas").get_data(as_text=True)
    assert "Texika SAS" in agrupado and "NIKOTEX" in agrupado


def test_excel_con_lo_filtrado(cliente):
    r = cliente.get("/deudas/excel?ver=todas&q=nk")
    hoja = load_workbook(io.BytesIO(r.data)).active
    filas = list(hoja.iter_rows(values_only=True))
    assert filas[0][:3] == ("Proveedor", "Factura", "Etiqueta")
    assert filas[1][:2] == ("NIKOTEX", "NK46") and filas[1][9] == "Pagada"
    assert filas[-1][0] == "Totales" and filas[-1][8] == 0
