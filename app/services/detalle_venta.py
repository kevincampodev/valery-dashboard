import json

from ..utils import a_pesos
from .mayoristas import normalizar_referencia


def _texto(valor):
    """Quita espacios sobrantes: '  azul   claro ' -> 'azul claro'"""
    return " ".join(str(valor or "").split())


def leer_detalle(texto_json, prendas):
    """
    Lee el detalle de prendas de una venta (un JSON que arma el formulario).
    Devuelve (lineas, error). Si no hay detalle devuelve ([], None): el detalle es opcional.
    """
    if not texto_json or not texto_json.strip():
        return [], None
    try:
        datos = json.loads(texto_json)
    except ValueError:
        return [], "el detalle de prendas llegó dañado."
    if not isinstance(datos, list):
        return [], "el detalle de prendas llegó dañado."
    if not datos:
        return [], None

    lineas = []
    for n, item in enumerate(datos, start=1):
        if not isinstance(item, dict):
            return [], "el detalle de prendas llegó dañado."
        referencia = normalizar_referencia(item.get("referencia"))
        cantidad = item.get("cantidad")
        cantidad = int(cantidad) if str(cantidad).strip().isdigit() else 0
        precio = a_pesos(str(item.get("precio") or ""))
        if not referencia or cantidad <= 0 or precio <= 0:
            return [], f"en el detalle, la prenda {n} necesita referencia, cantidad y precio."
        lineas.append({
            "referencia": referencia,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "color": _texto(item.get("color")).capitalize() or None,
            "talla": _texto(item.get("talla")).upper() or None,
        })

    suma = sum(l["cantidad"] for l in lineas)
    if suma != prendas:
        return [], f"el detalle suma {suma} prendas, pero la venta dice {prendas}."
    return lineas, None