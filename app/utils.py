import re
from datetime import date


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