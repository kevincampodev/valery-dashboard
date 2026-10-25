import os
import uuid

from flask import current_app

TAMANO_MAXIMO_FOTO = 2 * 1024 * 1024          # 2 MB
LARGO_NOMBRE = (2, 80)


def tipo_de_imagen(datos):
    """
    Reconoce la imagen por sus primeros bytes, no por la extensión del nombre
    (un archivo 'foto.jpg' puede ser cualquier cosa). Devuelve 'jpg', 'png', 'webp' o None.
    """
    if datos.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    return None


def carpeta_perfiles():
    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "perfiles")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def guardar_foto(archivo):
    """Valida y guarda la foto. Devuelve (nombre_archivo, error)."""
    datos = archivo.read(TAMANO_MAXIMO_FOTO + 1)
    if len(datos) > TAMANO_MAXIMO_FOTO:
        return None, "La foto pesa más de 2 MB."
    tipo = tipo_de_imagen(datos)
    if not tipo:
        return None, "La foto debe ser JPG, PNG o WEBP."
    nombre = f"{uuid.uuid4().hex}.{tipo}"
    with open(os.path.join(carpeta_perfiles(), nombre), "wb") as destino:
        destino.write(datos)
    return nombre, None


def borrar_foto(nombre):
    if not nombre:
        return
    ruta = os.path.join(carpeta_perfiles(), os.path.basename(nombre))
    if os.path.exists(ruta):
        os.remove(ruta)


def validar_nombre(nombre):
    nombre = " ".join((nombre or "").split())
    minimo, maximo = LARGO_NOMBRE
    if not minimo <= len(nombre) <= maximo:
        return None, f"El nombre debe tener entre {minimo} y {maximo} caracteres."
    return nombre, None
