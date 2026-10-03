import re


def normalizar_telefono(texto):
    """
    Limpia un teléfono colombiano y lo deja en 10 dígitos.
    '+57 300 123 4567' -> '3001234567'. Si no es un número válido, devuelve None.
    """
    digitos = re.sub(r"\D", "", str(texto or ""))
    if len(digitos) == 12 and digitos.startswith("57"):
        digitos = digitos[2:]                       # quita el indicativo de Colombia
    if len(digitos) == 10 and (digitos.startswith("3") or digitos.startswith("60")):
        return digitos                              # celular (3xx) o fijo (60x)
    return None


def formato_telefono(telefono):
    """'3001234567' -> '300 123 4567', para mostrarlo en pantalla."""
    if not telefono or len(telefono) != 10:
        return telefono or ""
    return f"{telefono[:3]} {telefono[3:6]} {telefono[6:]}"