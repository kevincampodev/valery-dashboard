def distribuir_fifo(facturas, valor):
    """
    Reparte `valor` entre las facturas, empezando por la de fecha límite más antigua.
    Devuelve ([(factura, monto), ...], sobrante).
    """
    plan, restante = [], valor
    for factura in sorted(facturas, key=lambda f: f.fecha_limite):
        if restante <= 0:
            break
        monto = min(restante, factura.saldo)
        if monto > 0:
            plan.append((factura, monto))
            restante -= monto
    return plan, restante