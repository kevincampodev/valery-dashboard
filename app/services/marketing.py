import calendar
from datetime import timedelta

# Medios de contacto que cuentan como clientes traídos por la publicidad pagada
REDES_PAUTA = ["TikTok", "Facebook", "Instagram"]
# Dónde se paga la pauta. Meta = una sola campaña para Facebook e Instagram.
PLATAFORMAS_PAUTA = ["TikTok", "Meta"]


def meses_entre(desde, hasta):
    """Primer día de cada mes entre `desde` y `hasta` (ambos incluidos)."""
    meses, mes = [], desde.replace(day=1)
    while mes <= hasta:
        meses.append(mes)
        mes = (mes.replace(day=28) + timedelta(days=4)).replace(day=1)
    return meses


def dias_pauta(mes, dias_config, hoy):
    """Días de pauta que cuentan en el mes: los configurados o todos; el mes en curso solo hasta hoy."""
    if mes > hoy:
        return 0
    dias = dias_config or calendar.monthrange(mes.year, mes.month)[1]
    if (mes.year, mes.month) == (hoy.year, hoy.month):
        dias = min(dias, hoy.day)
    return dias


def inversion_del_mes(pautas, mes, hoy):
    """Suma lo invertido en todas las plataformas de un mes (cada una con sus días)."""
    return sum(p.valor_diario * dias_pauta(mes, p.dias, hoy) for p in pautas)


def retorno_equilibrio(margen_bp):
    """Cuánto hay que vender por cada $1 de pauta para no perder (sin contar comisiones)."""
    return round(10000 / margen_bp, 2) if margen_bp else None


def rentabilidad(ventas, inversion, comisiones, margen_bp):
    ganancia_bruta = ventas * margen_bp // 10000
    resultado = ganancia_bruta - comisiones - inversion
    if not inversion:
        estado = "sin pauta"
    else:
        estado = "rentable" if resultado > 0 else "pérdida"
    return {
        "ventas": ventas,
        "inversion": inversion,
        "ganancia_bruta": ganancia_bruta,
        "comisiones": comisiones,
        "resultado": resultado,
        "retorno": round(ventas / inversion, 2) if inversion else None,
        "estado": estado,
    }