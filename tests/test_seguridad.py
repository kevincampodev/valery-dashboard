from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.seguridad import (registrar_intento_fallido, registrar_ingreso_exitoso, esta_bloqueado,
                                    minutos_restantes, validar_password, normalizar_usuario, MAX_INTENTOS)

AHORA = datetime(2026, 10, 3, 10, 0)


def _usuario():
    return SimpleNamespace(intentos_fallidos=0, bloqueado_hasta=None, ultimo_acceso=None)


def test_bloqueo_al_quinto_intento():
    u = _usuario()
    for _ in range(MAX_INTENTOS - 1):
        assert registrar_intento_fallido(u, AHORA) is False
    assert not esta_bloqueado(u, AHORA)

    assert registrar_intento_fallido(u, AHORA) is True      # el quinto bloquea
    assert esta_bloqueado(u, AHORA)
    assert minutos_restantes(u, AHORA) == 15
    assert u.intentos_fallidos == 0                          # el contador vuelve a cero


def test_el_bloqueo_vence_solo():
    u = _usuario()
    u.bloqueado_hasta = AHORA + timedelta(minutes=15)
    assert not esta_bloqueado(u, AHORA + timedelta(minutes=16))
    assert minutos_restantes(u, AHORA + timedelta(minutes=14, seconds=30)) == 1   # 30 segundos = "1 minuto"


def test_ingreso_exitoso_reinicia_los_intentos():
    u = _usuario()
    u.intentos_fallidos = 3
    registrar_ingreso_exitoso(u, AHORA)
    assert u.intentos_fallidos == 0 and u.ultimo_acceso == AHORA


def test_validar_password():
    assert validar_password("Tela2026Cali", "brayan", "Brayan Campo") == []
    assert "Debe tener al menos 10 caracteres." in validar_password("abc123")
    assert "Debe combinar letras y números." in validar_password("solamenteletras")
    assert "Es una contraseña demasiado común." in validar_password("1234567890")
    assert "No puede contener tu usuario ni tu nombre." in validar_password("brayan2026xx", "brayan")
    assert "No puede ser un mismo carácter repetido." in validar_password("aaaaa11111")


def test_normalizar_usuario():
    assert normalizar_usuario("  Alejo ") == "alejo"