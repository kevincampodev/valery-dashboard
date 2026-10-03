import math
from datetime import timedelta

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15
LARGO_MINIMO = 10
CONTRASENAS_COMUNES = {
    "1234567890", "12345678910", "0123456789", "contraseña", "contrasena", "password", "password1",
    "qwertyuiop", "administrador", "valeryfashion", "danyfashion", "disvaleryfashion",
}


def normalizar_usuario(texto):
    return (texto or "").strip().lower()


def esta_bloqueado(usuario, ahora):
    return bool(usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora)


def minutos_restantes(usuario, ahora):
    if not esta_bloqueado(usuario, ahora):
        return 0
    return math.ceil((usuario.bloqueado_hasta - ahora).total_seconds() / 60)


def registrar_intento_fallido(usuario, ahora):
    """Suma un intento fallido. Al llegar al máximo bloquea la cuenta y reinicia el contador. Devuelve True si quedó bloqueada."""
    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
    if usuario.intentos_fallidos >= MAX_INTENTOS:
        usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
        usuario.intentos_fallidos = 0
        return True
    return False


def registrar_ingreso_exitoso(usuario, ahora):
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora


def validar_password(password, usuario="", nombre=""):
    """Devuelve la lista de problemas de la contraseña. Lista vacía = contraseña aceptable."""
    password = password or ""
    errores = []
    if len(password) < LARGO_MINIMO:
        errores.append(f"Debe tener al menos {LARGO_MINIMO} caracteres.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        errores.append("Debe combinar letras y números.")
    if len(set(password)) <= 2:
        errores.append("No puede ser un mismo carácter repetido.")
    minuscula = password.lower()
    if minuscula in CONTRASENAS_COMUNES:
        errores.append("Es una contraseña demasiado común.")
    for palabra in (usuario, *(nombre or "").split()):
        palabra = (palabra or "").strip().lower()
        if len(palabra) >= 3 and palabra in minuscula:
            errores.append("No puede contener tu usuario ni tu nombre.")
            break
    return errores