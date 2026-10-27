"""
Pasa al panel lo que dice el Excel de facturas.

- Factura nueva (su número no está en el panel): se crea.
- Factura que ya está: se actualiza si el Excel cambió (prendas, descripciones, pagos, cliente, vendedora...).
  El Excel es la fuente de verdad de las facturas importadas.
"""
from datetime import datetime, time

from ..extensions import db
from ..models import Venta, Vendedora, Cliente, LineaVenta, PagoVenta, AbonoCliente
from .importador_facturas import VENDEDORA_MAYORISTA

TASA_COMISION_NUEVAS_BP = 200          # 2 %


def _lineas(lista):
    return [(l["referencia"], l["descripcion"], l["cantidad"], l["precio_unitario"], l["color"])
            if isinstance(l, dict) else
            (l.referencia, l.descripcion, l.cantidad, l.precio_unitario, l.color) for l in lista]


def _pagos(venta):
    return {p.medio: p.valor for p in venta.pagos}


def diferencias(venta, dato):
    """Qué cambió entre la venta guardada y el Excel."""
    cambios = []
    if _lineas(venta.lineas) != _lineas(dato["lineas"]):
        cambios.append("prendas")
    if _pagos(venta) != dato["pagos"]:
        cambios.append("pagos")
    if (venta.vendedora.nombre.lower() if venta.vendedora else None) != ((dato["vendedora"] or "").lower() or None):
        cambios.append("vendedora")
    cliente = venta.cliente
    # El cliente se identifica por su celular; solo sin celular se compara el nombre.
    if dato["telefono"]:
        otro_cliente = not cliente or cliente.telefono != dato["telefono"]
    elif dato["cliente"]:
        otro_cliente = not cliente or cliente.telefono or cliente.nombre.lower() != dato["cliente"].lower()
    else:
        otro_cliente = cliente is not None
    if otro_cliente:
        cambios.append("cliente")
    elif cliente and not cliente.autoriza_datos:
        cambios.append("autorización")
    for campo, atributo in (("fecha", "fecha"), ("valor", "valor"), ("prendas", "prendas"),
                            ("medio_contacto", "medio_contacto"), ("canal", "canal")):
        if getattr(venta, atributo) != dato[campo] and campo not in cambios:
            cambios.append(campo)
    return cambios


def planear(ventas, abonos):
    """Solo lee: qué se crearía y qué se actualizaría."""
    existentes = {v.numero_factura: v for v in Venta.query.filter(Venta.numero_factura.isnot(None))}
    nuevas, actualizar, iguales = [], [], 0
    for dato in ventas:
        venta = existentes.get(dato["numero"])
        if not venta:
            nuevas.append(dato)
            continue
        cambios = diferencias(venta, dato)
        if cambios:
            actualizar.append((venta, dato, cambios))
        else:
            iguales += 1

    ya_abonos = {n for (n,) in db.session.query(AbonoCliente.numero_factura)
                 .filter(AbonoCliente.numero_factura.isnot(None))}
    vendedoras = {v.nombre.lower() for v in Vendedora.query}
    nombres = {d["vendedora"] for d in ventas if d["vendedora"]}
    return {
        "nuevas": nuevas,
        "actualizar": actualizar,
        "iguales": iguales,
        "abonos": [a for a in abonos if a["numero"] not in ya_abonos],
        "vendedoras_nuevas": sorted(n for n in nombres if n.lower() not in vendedoras),
    }


class _Clientes:
    """Encuentra o crea el cliente de cada factura sin duplicarlo."""

    def __init__(self):
        self.vistos = {}

    def para(self, dato, actual=None):
        nombre, telefono = dato["cliente"], dato["telefono"]
        if not nombre and not telefono:
            return None
        clave = telefono or ("nombre", nombre.lower())
        cliente = self.vistos.get(clave)
        if not cliente and telefono:
            cliente = Cliente.query.filter_by(telefono=telefono).first()
        if not cliente and actual and not actual.telefono and nombre and actual.nombre.lower() == nombre.lower():
            cliente = actual
        if not cliente:
            cliente = Cliente(nombre=nombre or f"Cliente {telefono}", telefono=telefono, es_mayorista=False)
            db.session.add(cliente)
        if nombre and cliente.nombre.startswith("Cliente "):
            cliente.nombre = nombre
        # La tienda pide la autorización de datos en persona al hacer la factura (Ley 1581)
        if not cliente.autoriza_datos:
            cliente.autoriza_datos = True
            cliente.fecha_autorizacion = datetime.combine(dato["fecha"], time(12))
        if dato["canal"] == "Mayorista":
            cliente.es_mayorista = True
        self.vistos[clave] = cliente
        return cliente


def _llenar(venta, dato, vendedoras, clientes):
    medios = list(dato["pagos"])
    venta.fecha = dato["fecha"]
    venta.canal = dato["canal"]
    venta.valor = dato["valor"]
    venta.prendas = dato["prendas"]
    venta.medio_pago = medios[0] if len(medios) == 1 else "Mixto"
    venta.medio_contacto = dato["medio_contacto"]
    venta.numero_factura = dato["numero"]
    venta.vendedora = vendedoras.get((dato["vendedora"] or "").lower())
    venta.cliente = clientes.para(dato, venta.cliente)
    if _lineas(venta.lineas) != _lineas(dato["lineas"]):
        venta.lineas.clear()
        venta.lineas.extend(LineaVenta(**linea) for linea in dato["lineas"])
    if _pagos(venta) != dato["pagos"]:
        venta.pagos.clear()
        venta.pagos.extend(PagoVenta(medio=m, valor=v) for m, v in dato["pagos"].items())


def aplicar(plan):
    vendedoras = {v.nombre.lower(): v for v in Vendedora.query}
    for nombre in plan["vendedoras_nuevas"]:
        mayorista = nombre == VENDEDORA_MAYORISTA
        nueva = Vendedora(nombre=nombre, activa=True, vende_mayorista=mayorista,
                          tasa_comision_bp=0 if mayorista else TASA_COMISION_NUEVAS_BP)
        db.session.add(nueva)
        vendedoras[nombre.lower()] = nueva

    clientes = _Clientes()
    # Sin autoflush: las ventas se guardan juntas al final (los clientes repetidos los resuelve _Clientes)
    with db.session.no_autoflush:
        for venta, dato, _ in plan["actualizar"]:
            _llenar(venta, dato, vendedoras, clientes)
        for dato in plan["nuevas"]:
            venta = Venta(origen="factura")
            db.session.add(venta)
            _llenar(venta, dato, vendedoras, clientes)
    for dato in plan["abonos"]:
        db.session.add(AbonoCliente(fecha=dato["fecha"], valor=dato["valor"], medio=dato["medio"],
                                    numero_factura=dato["numero"], notas="Abono a saldo (importado del Excel)"))
    db.session.commit()
