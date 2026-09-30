from datetime import timedelta


def resumen_deudas(facturas):
    pendientes = [f for f in facturas if f.saldo > 0]
    vencidas = [f for f in pendientes if f.estado == "vencida"]
    por_vencer = [f for f in pendientes if f.estado == "por vencer"]
    return {
        "deuda_total": sum(f.saldo for f in pendientes),
        "vencido": sum(f.saldo for f in vencidas),
        "n_vencidas": len(vencidas),
        "por_vencer": sum(f.saldo for f in por_vencer),
        "n_por_vencer": len(por_vencer),
        "urgentes": sorted(vencidas + por_vencer, key=lambda f: f.fecha_limite),
    }


def deuda_por_proveedor(facturas):
    totales = {}
    for f in facturas:
        if f.saldo > 0:
            totales[f.proveedor.nombre] = totales.get(f.proveedor.nombre, 0) + f.saldo
    return sorted(totales.items(), key=lambda x: -x[1])


def vencimientos_por_semana(facturas, hoy, semanas=8):
    """
    Agrupa los saldos por semana (lunes a domingo) desde la semana actual.
    Columna 0 = todo lo ya vencido; última columna = lo que vence después del horizonte.
    """
    lunes = hoy - timedelta(days=hoy.weekday())
    etiquetas = (["Vencido"]
                 + [(lunes + timedelta(weeks=i)).strftime("%d/%m") for i in range(semanas)]
                 + ["Después"])
    valores = [0] * len(etiquetas)

    for f in facturas:
        if f.saldo <= 0:
            continue
        if f.fecha_limite < hoy:
            i = 0
        else:
            semana = (f.fecha_limite - lunes).days // 7
            i = semana + 1 if semana < semanas else len(etiquetas) - 1
        valores[i] += f.saldo

    return etiquetas, valores


def clientes_sin_comprar(clientes, hoy, dias=45, limite=5):
    """
    clientes: lista de (cliente, fecha_ultima_compra, total_comprado).
    Devuelve los que llevan más de `dias` sin comprar, del más olvidado al más reciente.
    """
    frios = []
    for cliente, ultima, total in clientes:
        if ultima and (hoy - ultima).days > dias:
            frios.append({"cliente": cliente, "ultima": ultima, "total": total, "dias": (hoy - ultima).days})
    return sorted(frios, key=lambda x: -x["dias"])[:limite]