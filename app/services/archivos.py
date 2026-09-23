import os
import uuid
from flask import current_app

EXTENSIONES_PERMITIDAS = {"pdf", "xml", "jpg", "jpeg", "png"}


def extension(nombre):
    return nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""


def guardar_archivo(archivo, subcarpeta):
    ext = extension(archivo.filename)
    if ext not in EXTENSIONES_PERMITIDAS:
        raise ValueError(f"Tipo de archivo no permitido: {archivo.filename}")

    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], subcarpeta)
    os.makedirs(carpeta, exist_ok=True)

    nombre_guardado = f"{uuid.uuid4().hex}.{ext}"
    archivo.save(os.path.join(carpeta, nombre_guardado))
    return f"{subcarpeta}/{nombre_guardado}", ext