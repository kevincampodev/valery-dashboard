"""
Un solo lugar con todas las secciones del panel.

De aquí salen el menú lateral, la pestaña "Todas las secciones", el buscador (Ctrl + K) y la barra
inferior del celular. Para agregar o mover una sección se cambia solo esta lista.
Cada usuario ve únicamente lo que su rol permite (puede_ver).
"""
from collections import namedtuple
from datetime import date, timedelta

from flask import g, request
from sqlalchemy import func

from .permisos import puede_ver, ve_todo

Seccion = namedtuple("Seccion", "endpoint icono nombre descripcion color")

# color: par de tonos para el ícono tipo app (de claro a oscuro)
GENERAL = [
    Seccion("dashboard.index", "house", "Inicio", "Resumen del día, alertas y pendientes", ("#4a8fd6", "#0f4c81")),
    Seccion("dashboard.aplicaciones", "layout-grid", "Todas las secciones", "Todo el panel en una sola vista", ("#8e99a8", "#5b6676")),
]

SECCIONES = [
    ("Ventas", [
        Seccion("ventas.index", "shopping-bag", "Ventas diarias", "Registra y analiza las ventas", ("#3d8fe0", "#1d5fb0")),
        Seccion("clientes.index", "contact-round", "Clientes", "Base de clientes y su historial", ("#9aa6b8", "#66748a")),
        Seccion("mayoristas.index", "store", "Mayoristas", "Clientes y precios al por mayor", ("#2fbfb1", "#0f8a80")),
    ]),
    ("Equipo", [
        Seccion("metas.index", "target", "Metas", "Metas del mes e incentivos", ("#ff7a66", "#e0412f")),
        Seccion("comisiones.index", "users-round", "Comisiones", "Comisiones por vendedora", ("#45cf72", "#1f9d55")),
    ]),
    ("Marketing", [
        Seccion("marketing.index", "megaphone", "Publicidad", "Pauta y rentabilidad", ("#ffae33", "#f07c00")),
        Seccion("redes.index", "trending-up", "Resumen de redes", "Ventas por TikTok, Facebook e Instagram", ("#cf7ae0", "#8e44ad")),
        Seccion("redes.facturas", "file-text", "Facturas por redes", "Facturas que llegaron por redes", ("#7d8bf5", "#4453c9")),
    ]),
    ("Proveedores", [
        Seccion("pagos.index", "calendar-clock", "Pagos pendientes", "Qué pagar y cuándo", ("#ffd04d", "#eda100")),
        Seccion("deudas.index", "receipt-text", "Deudas", "Facturas de proveedores", ("#ff7d93", "#d63a55")),
        Seccion("abonos.index", "hand-coins", "Abonos", "Pagos hechos a proveedores", ("#4fd6a0", "#14a37a")),
        Seccion("proyecciones.index", "chart-line", "Proyecciones", "Flujo de caja hacia adelante", ("#5ccbf2", "#1688c9")),
    ]),
    ("Administración", [
        Seccion("documentos.index", "folder-open", "Documentos", "Archivos de la empresa", ("#69b7ff", "#2b7de9")),
        Seccion("reportes.index", "file-spreadsheet", "Reportes", "Informes para descargar", ("#7b8794", "#3f4954")),
        Seccion("sistema.index", "shield-check", "Sistema", "Usuarios, copias y seguridad", ("#a9b0bb", "#6b7280")),
    ]),
]

# Barra inferior del celular: las primeras 3 que el usuario pueda ver, más el botón "Más"
PREFERIDAS_MOVIL = ["dashboard.index", "ventas.index", "pagos.index", "redes.index", "redes.facturas", "marketing.index"]
CORTOS = {"dashboard.index": "Inicio", "ventas.index": "Ventas", "pagos.index": "Pagos",
          "redes.index": "Redes", "redes.facturas": "Facturas", "marketing.index": "Publicidad"}
DIAS_SIN_COMPRA = 45


def es_activo(endpoint):
    """La sección de la página actual. Redes e Inicio tienen varias páginas en el mismo módulo: se comparan exactas."""
    if endpoint.startswith(("redes.", "dashboard.")):
        return request.endpoint == endpoint
    return request.blueprint == endpoint.split(".")[0]


def hoy_iso():
    return date.today().isoformat()


def general_visible():
    return [s for s in GENERAL if puede_ver(s.endpoint)]


def secciones_visibles():
    """[(titulo, [Seccion...])] solo con lo que el rol actual puede ver; los grupos vacíos no salen."""
    salida = []
    for titulo, items in SECCIONES:
        visibles = [s for s in items if puede_ver(s.endpoint)]
        if visibles:
            salida.append((titulo, visibles))
    return salida


def barra_movil():
    todas = {s.endpoint: s for s in GENERAL + [s for _, items in SECCIONES for s in items]}
    elegidas = [todas[e] for e in PREFERIDAS_MOVIL if e in todas and puede_ver(e)][:3]
    return [(s, CORTOS.get(s.endpoint, s.nombre)) for s in elegidas]


def contadores():
    """
    Números pequeños al lado de cada sección: {endpoint: (texto, tipo)}.
    Se calculan una sola vez por página y solo para quien ve todo el panel.
    """
    if "contadores_menu" in g:
        return g.contadores_menu
    salida = {}
    if ve_todo():
        try:
            salida = _calcular_contadores(date.today())
        except Exception:      # el menú nunca debe tumbar una página
            salida = {}
    g.contadores_menu = salida
    return salida


def _calcular_contadores(hoy):
    from ..extensions import db
    from ..models import Factura, Venta, Cliente
    from sqlalchemy.orm import selectinload

    salida = {}
    facturas = Factura.query.options(selectinload(Factura.aplicaciones)).all()
    vencidas = sum(1 for f in facturas if f.saldo > 0 and f.estado == "vencida")
    if vencidas:
        salida["pagos.index"] = (str(vencidas), "peligro", f"{vencidas} factura{'s' if vencidas != 1 else ''} vencida{'s' if vencidas != 1 else ''}")

    ultima = db.session.query(func.max(Venta.fecha)).filter(Venta.fecha >= hoy.replace(day=1)).scalar()
    if (ultima and (hoy - ultima).days > 1) or (not ultima and hoy.day > 1):
        salida["ventas.index"] = ("", "aviso", "Hay días sin ventas cargadas")

    limite = hoy - timedelta(days=DIAS_SIN_COMPRA)
    ultimas = (db.session.query(Venta.cliente_id, func.max(Venta.fecha).label("ultima"))
               .join(Cliente, Cliente.id == Venta.cliente_id).filter(Cliente.activo.is_(True))
               .group_by(Venta.cliente_id).subquery())
    frios = db.session.query(func.count()).select_from(ultimas).filter(ultimas.c.ultima < limite).scalar()
    if frios:
        salida["clientes.index"] = (str(frios), "info", f"{frios} cliente{'s' if frios != 1 else ''} sin volver hace +{DIAS_SIN_COMPRA} días")
    return salida
