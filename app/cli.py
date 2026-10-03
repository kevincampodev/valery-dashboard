import random
import re
import secrets
import string
from datetime import date, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.orm import joinedload

from .extensions import db
from .services.backups import crear_backup
from .services.importador_ventas import leer_revision, resumir
from .services.seguridad import normalizar_usuario, validar_password
from .services.mayoristas import es_mayorista, UMBRAL_MAYORISTA_DEFECTO
from .utils import formato_pesos
from .models import (Proveedor, Factura, Pago, AplicacionPago, Vendedora, Venta, Liquidacion, Meta,
                     TramoIncentivo, Objetivo, CuentaDinero, GastoRecurrente, AjusteTemporada, MEDIOS_PAGO,
                     Parametro, Usuario)
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


@click.command("importar-ventas")
@click.argument("archivo", type=click.Path(exists=True, dir_okay=False))
@click.option("--confirmar", is_flag=True, help="Guarda los cambios. Sin esta opción solo muestra la vista previa.")
@click.option("--borrar-manuales", is_flag=True, help="Borra también las ventas registradas a mano en el mismo rango de fechas.")
@with_appcontext
def importar_ventas(archivo, confirmar, borrar_manuales):
    """Importa ventas desde el archivo de revisión (hoja 'Ventas')."""
    try:
        ventas, omitidas = leer_revision(archivo)
    except ValueError as e:
        raise click.ClickException(str(e))
    if not ventas:
        raise click.ClickException("No se encontró ninguna venta para importar.")

    desde = min(v["fecha"] for v in ventas)
    hasta = max(v["fecha"] for v in ventas)
    total = sum(v["valor"] for v in ventas)
    click.echo(f"\n{len(ventas)} ventas por {formato_pesos(total)}, del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}")
    for titulo, grupo in resumir(ventas).items():
        click.echo(f"\n{titulo}")
        for clave, valor in grupo.items():
            click.echo(f"  {clave:<22}{formato_pesos(valor):>18}")
    if omitidas:
        click.secho(f"\n{len(omitidas)} fila(s) omitida(s):", fg="yellow")
        for fila, motivo in omitidas:
            click.echo(f"  Fila {fila}: {motivo}")

    vendedoras = {v.nombre.lower(): v for v in Vendedora.query.all()}
    nuevas = sorted({v["vendedora"] for v in ventas
                     if v["vendedora"] and v["vendedora"].lower() not in vendedoras})
    if nuevas:
        click.echo(f"\nVendedoras nuevas (se crearán inactivas): {', '.join(nuevas)}")

    rango = Venta.query.filter(Venta.fecha.between(desde, hasta))
    anteriores = rango.filter_by(origen="excel").all()
    manuales = rango.filter_by(origen="manual").all()
    if anteriores:
        click.echo(f"\nSe reemplazarán {len(anteriores)} ventas de una importación anterior.")
    if manuales:
        accion = "SE BORRARÁN" if borrar_manuales else "se conservarán (usa --borrar-manuales si eran de prueba)"
        click.secho(f"\nOjo: hay {len(manuales)} ventas registradas a mano en ese rango, por "
                    f"{formato_pesos(sum(v.neto for v in manuales))}: {accion}.", fg="yellow")

    if not confirmar:
        click.secho("\nVista previa: no se guardó nada. Para importar, repite el comando con --confirmar.", fg="cyan")
        return

    ruta_backup = crear_backup(current_app.config["DB_PATH"], current_app.config["BACKUP_DIR"])
    click.echo(f"\nBackup previo: {ruta_backup}")

    for nombre in nuevas:
        vendedora = Vendedora(nombre=nombre, activa=False)
        db.session.add(vendedora)
        vendedoras[nombre.lower()] = vendedora

    for venta in anteriores + (manuales if borrar_manuales else []):
        db.session.delete(venta)

    for dato in ventas:
        db.session.add(Venta(
            fecha=dato["fecha"], canal=dato["canal"], valor=dato["valor"], medio_pago="Otro",
            medio_contacto=dato["medio_contacto"], origen="excel",
            vendedora=vendedoras.get((dato["vendedora"] or "").lower()),
        ))
    db.session.commit()

    click.secho(f"\nListo: {len(ventas)} ventas importadas.", fg="green")
    if nuevas:
        click.echo("Activa en Ventas → Vendedoras a quienes sigan trabajando.")


@click.command("reclasificar-canal")
@click.option("--confirmar", is_flag=True, help="Guarda los cambios. Sin esta opción solo muestra la vista previa.")
@with_appcontext
def reclasificar_canal(confirmar):
    """Aplica la regla de venta mayorista a las ventas importadas desde Excel."""
    if not Vendedora.query.filter_by(vende_mayorista=True).first():
        raise click.ClickException("Nadie tiene permiso de venta mayorista. Actívalo en Ventas → Vendedoras primero.")

    umbral = Parametro.obtener_int("umbral_mayorista", UMBRAL_MAYORISTA_DEFECTO)
    ventas = Venta.query.options(joinedload(Venta.vendedora)).filter_by(origen="excel", es_devolucion=False).all()

    cambios = []
    for venta in ventas:
        permiso = venta.vendedora.vende_mayorista if venta.vendedora else False
        nuevo = "Mayorista" if es_mayorista(permiso, venta.valor, umbral) else "Minorista"
        if nuevo != venta.canal:
            cambios.append((venta, nuevo))

    a_minorista = [v for v, nuevo in cambios if nuevo == "Minorista"]
    a_mayorista = [v for v, nuevo in cambios if nuevo == "Mayorista"]
    click.echo(f"\nRegla: mayorista si la vende alguien con permiso y pasa de {formato_pesos(umbral)}.")
    click.echo(f"  Pasan a minorista: {len(a_minorista):>4} ventas  {formato_pesos(sum(v.valor for v in a_minorista)):>16}")
    click.echo(f"  Pasan a mayorista: {len(a_mayorista):>4} ventas  {formato_pesos(sum(v.valor for v in a_mayorista)):>16}")

    if not cambios:
        click.secho("\nNo hay nada que cambiar.", fg="green")
        return
    if not confirmar:
        click.secho("\nVista previa: no se guardó nada. Para aplicar, repite el comando con --confirmar.", fg="cyan")
        return

    ruta_backup = crear_backup(current_app.config["DB_PATH"], current_app.config["BACKUP_DIR"])
    click.echo(f"\nBackup previo: {ruta_backup}")
    for venta, nuevo in cambios:
        venta.canal = nuevo
    db.session.commit()
    click.secho(f"Listo: {len(cambios)} ventas reclasificadas.", fg="green")


def _password_temporal():
    alfabeto = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alfabeto) for _ in range(14))
        if not validar_password(password):
            return password


def _buscar_usuario(usuario):
    encontrado = Usuario.query.filter_by(usuario=normalizar_usuario(usuario)).first()
    if not encontrado:
        raise click.ClickException(f"No existe el usuario '{usuario}'.")
    return encontrado


@click.command("crear-usuario")
@click.argument("usuario")
@click.option("--nombre", prompt="Nombre completo", help="Nombre que se muestra en el menú.")
@with_appcontext
def crear_usuario(usuario, nombre):
    """Crea un administrador con una contraseña temporal."""
    usuario = normalizar_usuario(usuario)
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", usuario):
        raise click.ClickException("El usuario debe tener de 3 a 40 caracteres: letras, números, punto, guion o guion bajo.")
    if Usuario.query.filter_by(usuario=usuario).first():
        raise click.ClickException(f"Ya existe el usuario '{usuario}'.")

    password = _password_temporal()
    nuevo = Usuario(usuario=usuario, nombre=nombre.strip(), debe_cambiar_password=True)
    nuevo.fijar_password(password)
    db.session.add(nuevo)
    db.session.commit()

    click.secho(f"\nUsuario '{usuario}' creado.", fg="green")
    click.echo(f"Contraseña temporal: {password}")
    click.secho("Entrégasela en persona. Al ingresar deberá cambiarla y activar la verificación en dos pasos.", fg="yellow")


@click.command("reiniciar-2fa")
@click.argument("usuario")
@with_appcontext
def reiniciar_2fa(usuario):
    """Quita la verificación en dos pasos (por ejemplo, si perdió el celular)."""
    encontrado = _buscar_usuario(usuario)
    encontrado.totp_activo = False
    encontrado.totp_secreto = None
    encontrado.version_sesion += 1
    db.session.commit()
    click.secho(f"2FA reiniciado para '{encontrado.usuario}'. Deberá activarlo de nuevo al ingresar.", fg="green")


@click.command("desbloquear-usuario")
@click.argument("usuario")
@with_appcontext
def desbloquear_usuario(usuario):
    """Quita el bloqueo por intentos fallidos."""
    encontrado = _buscar_usuario(usuario)
    encontrado.intentos_fallidos = 0
    encontrado.bloqueado_hasta = None
    db.session.commit()
    click.secho(f"'{encontrado.usuario}' desbloqueado.", fg="green")


@click.command("desactivar-usuario")
@click.argument("usuario")
@click.option("--reactivar", is_flag=True, help="Vuelve a activar un usuario desactivado.")
@with_appcontext
def desactivar_usuario(usuario, reactivar):
    """Desactiva (o reactiva) un usuario. Desactivar cierra sus sesiones al instante."""
    encontrado = _buscar_usuario(usuario)
    encontrado.activo = reactivar
    encontrado.version_sesion += 1
    db.session.commit()
    click.secho(f"'{encontrado.usuario}' {'reactivado' if reactivar else 'desactivado'}.", fg="green")