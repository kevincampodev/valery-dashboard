import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def a_pesos(texto):
    """'10.115.058' -> 10115058 | '42.521,01' -> 42521"""
    entero = (texto or "").split(",")[0]
    digitos = re.sub(r"\D", "", entero)
    return int(digitos) if digitos else 0


def a_fecha(texto):
    return date.fromisoformat(texto) if texto else None

def nit_base(nit):
    """'890.301.753-9' -> '890301753' (sin puntos ni dígito de verificación)"""
    if not nit:
        return ""
    return re.sub(r"\D", "", nit.split("-")[0])


def normalizar(texto):
    """'LAZCHAV S.A.S' -> 'lazchavsas'"""
    return re.sub(r"[^a-z0-9]", "", (texto or "").lower())


def formato_pesos(valor):
    return "$" + f"{int(valor or 0):,}".replace(",", ".")


def mes_desde_texto(texto):
    """'2026-09' -> date(2026, 9, 1). Si viene vacío o inválido, el mes actual."""
    try:
        return date.fromisoformat(f"{texto}-01")
    except (TypeError, ValueError):
        return date.today().replace(day=1)


def rango_mes(inicio):
    """date(2026, 9, 1) -> (date(2026, 9, 1), date(2026, 9, 30))"""
    ultimo = calendar.monthrange(inicio.year, inicio.month)[1]
    return inicio, inicio.replace(day=ultimo)


def nombre_mes(fecha):
    return f"{MESES[fecha.month - 1].capitalize()} {fecha.year}"


def a_bp(texto):
    """'0,5' -> 50 puntos básicos | '1.25' -> 125"""
    try:
        return int((Decimal((texto or "0").replace(",", ".")) * 100).quantize(Decimal("1")))
    except InvalidOperation:
        return 0


def formato_bp(bp):
    """50 -> '0,5%' | 125 -> '1,25%' | 100 -> '1%'"""
    return f"{(bp or 0) / 100:g}".replace(".", ",") + "%"