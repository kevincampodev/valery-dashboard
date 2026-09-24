import io
import zipfile
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from defusedxml.ElementTree import fromstring

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}
TAMANO_MAXIMO = 20 * 1024 * 1024  # ignora archivos internos de más de 20 MB
FORMAS_PAGO = {"1": "Contado", "2": "Crédito"}


def _texto(elemento, ruta):
    nodo = elemento.find(ruta, NS)
    return nodo.text.strip() if nodo is not None and nodo.text else None


def _pesos(texto):
    """'2036974.79' -> 2036975 (redondeo contable, sin float)"""
    if not texto:
        return 0
    return int(Decimal(texto).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _extension(nombre):
    return nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""


def parsear_xml(contenido):
    """Recibe los bytes de un XML DIAN y devuelve un dict con los datos de la factura."""
    raiz = fromstring(contenido)
    tipo = raiz.tag.rsplit("}", 1)[-1]  # '{namespace}AttachedDocument' -> 'AttachedDocument'

    if tipo == "AttachedDocument":
        texto = _texto(raiz, "cac:Attachment/cac:ExternalReference/cbc:Description")
        if not texto or "<Invoice" not in texto:
            raise ValueError("El XML no trae una factura de venta embebida")
        factura = fromstring(texto.encode("utf-8"))
    elif tipo == "Invoice":
        factura = raiz
    else:
        raise ValueError(f"Tipo de documento no soportado: {tipo}")

    totales = "cac:LegalMonetaryTotal/cbc:"
    emision = _texto(factura, "cbc:IssueDate")
    vence = (_texto(factura, "cbc:DueDate")
             or _texto(factura, "cac:PaymentMeans/cbc:PaymentDueDate")
             or emision)

    nit_nodo = factura.find(
        "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID", NS)
    nit = nit_nodo.text.strip() if nit_nodo is not None and nit_nodo.text else None
    dv = nit_nodo.get("schemeID") if nit_nodo is not None else None

    return {
        "numero": _texto(factura, "cbc:ID"),
        "cufe": _texto(factura, "cbc:UUID"),
        "fecha_emision": date.fromisoformat(emision),
        "fecha_vencimiento": date.fromisoformat(vence),
        "subtotal": _pesos(_texto(factura, totales + "LineExtensionAmount")),
        "iva": (_pesos(_texto(factura, totales + "TaxInclusiveAmount"))
                - _pesos(_texto(factura, totales + "TaxExclusiveAmount"))),
        "total": _pesos(_texto(factura, totales + "PayableAmount")),
        "forma_pago": FORMAS_PAGO.get(_texto(factura, "cac:PaymentMeans/cbc:ID"), "No indicada"),
        "proveedor_nombre": _texto(
            factura, "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:RegistrationName"),
        "proveedor_nit": f"{nit}-{dv}" if nit and dv else nit,
    }


def extraer_paquetes(nombre, contenido, profundidad=0):
    """
    Recorre un ZIP (incluso con ZIPs adentro) y devuelve una lista de paquetes:
    {"origen": nombre_zip, "xml": (nombre, bytes), "pdfs": [(nombre, bytes), ...]}
    """
    ext = _extension(nombre)
    if ext == "xml":
        return [{"origen": nombre, "xml": (nombre, contenido), "pdfs": []}]
    if ext != "zip" or profundidad > 3:
        return []

    paquetes, carpetas = [], {}
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        for info in z.infolist():
            if info.is_dir() or info.file_size > TAMANO_MAXIMO:
                continue
            carpeta, _, base = info.filename.rpartition("/")
            e = _extension(base)
            if e == "zip":
                paquetes += extraer_paquetes(base, z.read(info), profundidad + 1)
            elif e in ("xml", "pdf"):
                grupo = carpetas.setdefault(carpeta, {"xml": [], "pdf": []})
                grupo[e].append((base, z.read(info)))

    for grupo in carpetas.values():
        if len(grupo["xml"]) == 1:
            paquetes.append({"origen": nombre, "xml": grupo["xml"][0], "pdfs": grupo["pdf"]})
        else:
            # Varios XML en la misma carpeta: no sabemos qué PDF es de cuál
            paquetes += [{"origen": nombre, "xml": x, "pdfs": []} for x in grupo["xml"]]
    return paquetes