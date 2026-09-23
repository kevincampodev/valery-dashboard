import re
from datetime import date


def a_pesos(texto):
    """'10.115.058' -> 10115058 | '42.521,01' -> 42521"""
    entero = (texto or "").split(",")[0]
    digitos = re.sub(r"\D", "", entero)
    return int(digitos) if digitos else 0


def a_fecha(texto):
    return date.fromisoformat(texto) if texto else None