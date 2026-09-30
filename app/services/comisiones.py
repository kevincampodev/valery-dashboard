import calendar
from datetime import date

from ..utils import MESES

# Regla de la administración: solo las ventas minoristas generan comisión. Las mayoristas nunca.
CANAL_COMISIONABLE = "Minorista"


def quincena_de(fecha):
    """Devuelve (inicio, fin) de la quincena que contiene `fecha`: 1-15 o 16-último día."""
    if fecha.day <= 15:
        return date(fecha.year, fecha.month, 1), date(fecha.year, fecha.month, 15)
    ultimo = calendar.monthrange(fecha.year, fecha.month)[1]
    return date(fecha.year, fecha.month, 16), date(fecha.year, fecha.month, ultimo)


def etiqueta_quincena(inicio, fin):
    return f"{inicio.day}–{fin.day} de {MESES[inicio.month - 1]} {inicio.year}"


def calcular_comision(ventas_netas, tasa_bp, meta, bono_meta):
    base = max(ventas_netas, 0)  # si solo hubo devoluciones, no hay comisión negativa
    comision = base * tasa_bp // 10000
    cumple_meta = bool(meta) and ventas_netas >= meta
    bono = bono_meta if cumple_meta else 0
    return {"comision": comision, "bono": bono, "total": comision + bono, "cumple_meta": cumple_meta}