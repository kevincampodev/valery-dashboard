from app.services.clientes import normalizar_telefono, formato_telefono


def test_normaliza_distintas_formas_de_escribir():
    assert normalizar_telefono("300 123 4567") == "3001234567"
    assert normalizar_telefono("300-123-4567") == "3001234567"
    assert normalizar_telefono("+57 300 123 4567") == "3001234567"
    assert normalizar_telefono("(602) 555 1234") == "6025551234"     # fijo de Cali


def test_rechaza_numeros_invalidos():
    assert normalizar_telefono("") is None
    assert normalizar_telefono("300 123") is None                      # incompleto
    assert normalizar_telefono("1234567890") is None                   # no empieza por 3 ni 60


def test_formato_para_mostrar():
    assert formato_telefono("3001234567") == "300 123 4567"
    assert formato_telefono(None) == ""