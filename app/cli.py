import random
from datetime import date, timedelta

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import (Proveedor, Factura, Pago, AplicacionPago, Vendedora, Venta, Liquidacion, Meta,
                     TramoIncentivo, Objetivo, CuentaDinero, GastoRecurrente, AjusteTemporada, MEDIOS_PAGO)
from .services.abonos import distribuir_fifo
from .services.comisiones import quincena_de, calcular_comision


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """Llena una base de datos VACÍA con datos ficticios de demostración."""
    if Factura.query.first() or Venta.query.first():
        raise click.ClickException("La base ya tiene datos. Este comando solo corre sobre una base vacía.")

    rnd = random.Random(42)
    hoy = date.today()

    # Proveedores, facturas y abonos
    proveedores = [Proveedor(nombre=n, nit=nit, dias_credito=d) for n, nit, d in [
        ("Textiles Andinos SAS", "900111222-1", 60),
        ("Confecciones del Pacífico SAS", "900333444-2", 30),
        ("Moda Urbana Ltda", "900555666-3", 45),
        ("Hilos y Telas del Valle SAS", "900777888-4", 90),
    ]]
    db.session.add_all(proveedores)
    for i in range(14):
        proveedor = rnd.choice(proveedores)
        emision = hoy - timedelta(days=rnd.randint(5, 150))
        subtotal = rnd.randrange(2_000_000, 25_000_000, 1_000)
        iva = subtotal * 19 // 100
        db.session.add(Factura(
            proveedor=proveedor, numero=f"FE{1000 + i}", fecha_emision=emision,
            fecha_vencimiento=emision + timedelta(days=proveedor.dias_credito),
            subtotal=subtotal, iva=iva, total=subtotal + iva,
            etiqueta="Temporada diciembre" if i % 4 == 0 else None,
        ))

    for proveedor in proveedores:
        for _ in range(rnd.randint(1, 3)):
            pendientes = [f for f in proveedor.facturas if f.saldo > 0]
            if not pendientes:
                break
            plan, _ = distribuir_fifo(pendientes, rnd.randrange(1_000_000, 12_000_000, 50_000))
            pago = Pago(proveedor=proveedor, fecha=hoy - timedelta(days=rnd.randint(1, 60)),
                        valor=sum(m for _, m in plan), medio=rnd.choice(MEDIOS_PAGO))
            pago.aplicaciones.extend(AplicacionPago(factura=f, valor=m) for f, m in plan)
            db.session.add(pago)

    # Vendedoras y 120 días de ventas
    vendedoras = [Vendedora(nombre=n, tasa_comision_bp=t, meta_quincenal=m, bono_meta=b) for n, t, m, b in [
        ("Laura Gómez", 200, 9_000_000, 100_000),
        ("Camila Ríos", 200, 9_000_000, 100_000),
        ("Daniela Mejía", 150, None, 0),
        ("Valentina Cruz", 250, 7_000_000, 80_000),
    ]]
    db.session.add_all(vendedoras)

    factor_dia = [0.8, 0.7, 0.8, 0.9, 1.1, 1.6, 0.5]  # lunes a domingo
    medios = ["Efectivo", "Transferencia", "Datáfono"]
    ventas = []
    for n in range(120, 0, -1):
        dia = hoy - timedelta(days=n)
        for v in vendedoras:
            valor = int(max(0, rnd.gauss(700_000, 200_000) * factor_dia[dia.weekday()]) // 1_000 * 1_000)
            if valor:
                ventas.append(Venta(fecha=dia, canal="Minorista", vendedora=v, valor=valor, medio_pago=rnd.choice(medios)))
            if rnd.random() < 0.05:
                ventas.append(Venta(fecha=dia, canal="Minorista", vendedora=v, medio_pago="Efectivo",
                                    valor=rnd.randrange(50_000, 200_000, 1_000), es_devolucion=True))
        if rnd.random() < 0.4:
            ventas.append(Venta(fecha=dia, canal="Mayorista", valor=rnd.randrange(2_000_000, 8_000_000, 10_000),
                                medio_pago="Transferencia"))
    db.session.add_all(ventas)

    # Liquidaciones de las últimas 4 quincenas terminadas (la más reciente queda por pagar)
    inicio, fin = quincena_de(hoy)
    for i in range(4):
        inicio, fin = quincena_de(inicio - timedelta(days=1))
        for v in vendedoras:
            neto = sum(x.neto for x in ventas if x.vendedora is v and inicio <= x.fecha <= fin)
            calc = calcular_comision(neto, v.tasa_comision_bp, v.meta_quincenal, v.bono_meta)
            db.session.add(Liquidacion(
                vendedora=v, inicio=inicio, fin=fin, ventas_netas=neto, tasa_bp=v.tasa_comision_bp,
                meta=v.meta_quincenal, comision=calc["comision"], bono=calc["bono"], total=calc["total"],
                estado="pendiente" if i == 0 else "pagada",
                fecha_pago=None if i == 0 else fin + timedelta(days=1),
                medio_pago=None if i == 0 else "Efectivo",
            ))

    # Metas, incentivo, objetivos y finanzas
    mes = hoy.replace(day=1)
    db.session.add_all([Meta(periodo=mes, canal=c, valor=v) for c, v in
                        [("Total", 140_000_000), ("Minorista", 80_000_000), ("Mayorista", 60_000_000)]])
    db.session.add_all([TramoIncentivo(cumplimiento_min=90, tasa_bp=50),
                        TramoIncentivo(cumplimiento_min=100, tasa_bp=100),
                        TramoIncentivo(cumplimiento_min=110, tasa_bp=150, bono_fijo=300_000, descripcion="Tramo élite")])
    db.session.flush()
    db.session.add_all([
        Objetivo(titulo="Dejar Moda Urbana en cero", proveedor=proveedores[2],
                 saldo_inicial=proveedores[2].deuda_total, fecha_limite=hoy + timedelta(days=60)),
        Objetivo(titulo="Abrir tienda online", progreso_manual=40, fecha_limite=hoy + timedelta(days=90)),
    ])
    db.session.add_all([CuentaDinero(nombre="Caja", saldo=3_500_000),
                        CuentaDinero(nombre="Banco principal", saldo=18_000_000)])
    db.session.add_all([
        GastoRecurrente(nombre="Arriendo local", categoria="Arriendo", valor=4_500_000, frecuencia="mensual", dia=5),
        GastoRecurrente(nombre="Nómina", categoria="Nómina", valor=6_000_000, frecuencia="quincenal", dia=1),
        GastoRecurrente(nombre="Seguridad social", categoria="Seguridad social", valor=2_200_000, frecuencia="mensual", dia=10),
        GastoRecurrente(nombre="Servicios públicos", categoria="Servicios", valor=850_000, frecuencia="mensual", dia=20),
    ])
    db.session.add_all([AjusteTemporada(mes=m, factor_pct=f) for m, f in [(11, 130), (12, 180), (1, 70)]])

    db.session.commit()
    click.echo(f"Datos demo creados: {len(proveedores)} proveedores, 14 facturas, {len(ventas)} registros de venta.")