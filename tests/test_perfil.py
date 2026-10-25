from app.models import Usuario
from app.services.perfil import tipo_de_imagen, validar_nombre


def test_reconoce_la_imagen_por_su_contenido_y_no_por_el_nombre():
    assert tipo_de_imagen(b"\xff\xd8\xff\xe0" + b"0" * 20) == "jpg"
    assert tipo_de_imagen(b"\x89PNG\r\n\x1a\n" + b"0" * 20) == "png"
    assert tipo_de_imagen(b"RIFF1234WEBPVP8 ") == "webp"
    assert tipo_de_imagen(b"<svg onload=alert(1)>") is None      # un SVG podría traer código
    assert tipo_de_imagen(b"") is None


def test_nombre_del_perfil():
    assert validar_nombre("  Alejandro   Campo ") == ("Alejandro Campo", None)
    assert validar_nombre("A")[0] is None
    assert validar_nombre("x" * 81)[0] is None


def test_iniciales_para_el_avatar():
    assert Usuario(nombre="Alejandro Campo Lesama").iniciales == "AC"
    assert Usuario(nombre="brayan").iniciales == "B"
