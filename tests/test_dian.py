import io
import zipfile
from datetime import date

from app.services.dian import parsear_xml, extraer_paquetes

UBL = ('xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
       'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"')

FACTURA = f"""<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" {UBL}>
  <cbc:ID>FE999</cbc:ID>
  <cbc:UUID schemeID="1">cufe-de-prueba-123</cbc:UUID>
  <cbc:IssueDate>2026-09-01</cbc:IssueDate>
  <cbc:DueDate>2026-10-01</cbc:DueDate>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme>
    <cbc:RegistrationName>PROVEEDOR DEMO SAS</cbc:RegistrationName>
    <cbc:CompanyID schemeID="7">900123456</cbc:CompanyID>
  </cac:PartyTaxScheme></cac:Party></cac:AccountingSupplierParty>
  <cac:PaymentMeans><cbc:ID>2</cbc:ID></cac:PaymentMeans>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="COP">1000000.40</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="COP">1000000.40</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="COP">1190000.00</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="COP">1190000.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
</Invoice>"""

CONTENEDOR = f"""<?xml version="1.0" encoding="UTF-8"?>
<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" {UBL}>
  <cac:Attachment><cac:ExternalReference>
    <cbc:Description><![CDATA[{FACTURA}]]></cbc:Description>
  </cac:ExternalReference></cac:Attachment>
</AttachedDocument>""".encode("utf-8")


def test_lee_factura_embebida():
    datos = parsear_xml(CONTENEDOR)
    assert datos["numero"] == "FE999"
    assert datos["cufe"] == "cufe-de-prueba-123"
    assert datos["fecha_vencimiento"] == date(2026, 10, 1)
    assert datos["total"] == 1190000
    assert datos["subtotal"] == 1000000  # redondea los centavos
    assert datos["forma_pago"] == "Crédito"
    assert datos["proveedor_nit"] == "900123456-7"


def test_zip_dentro_de_zip_empareja_pdf():
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w") as z:
        z.writestr("ad123.xml", CONTENEDOR)
        z.writestr("fv123.pdf", b"%PDF-demo")

    externo = io.BytesIO()
    with zipfile.ZipFile(externo, "w") as z:
        z.writestr("PROVEEDOR/z123.zip", interno.getvalue())
        z.writestr("OTRO/suelto.pdf", b"%PDF-sin-xml")  # no debe pegarse a ninguna factura

    paquetes = extraer_paquetes("lote.zip", externo.getvalue())
    assert len(paquetes) == 1
    assert paquetes[0]["pdfs"][0][0] == "fv123.pdf"