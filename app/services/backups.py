import glob
import os
import sqlite3
from datetime import date, datetime

PREFIJO = "valery-"


def listar_backups(carpeta):
    rutas = glob.glob(os.path.join(carpeta, f"{PREFIJO}*.db"))
    backups = [{
        "nombre": os.path.basename(r),
        "tamano": os.path.getsize(r),
        "fecha": datetime.fromtimestamp(os.path.getmtime(r)),
    } for r in rutas]
    return sorted(backups, key=lambda b: b["nombre"], reverse=True)


def crear_backup(ruta_db, carpeta, conservar=30):
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, f"{PREFIJO}{datetime.now():%Y%m%d-%H%M%S}.db")

    origen = sqlite3.connect(ruta_db)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    origen.close()
    copia.close()

    for viejo in listar_backups(carpeta)[conservar:]:
        os.remove(os.path.join(carpeta, viejo["nombre"]))
    return destino


def hay_backup_de(carpeta, dia):
    return any(b["nombre"].startswith(f"{PREFIJO}{dia:%Y%m%d}") for b in listar_backups(carpeta))


def registrar_backup_diario(app):
    @app.before_request
    def _backup_diario():
        hoy = date.today()
        if app.config.get("_ULTIMO_BACKUP") == hoy:
            return
        ruta, carpeta = app.config["DB_PATH"], app.config["BACKUP_DIR"]
        if os.path.exists(ruta) and not hay_backup_de(carpeta, hoy):
            try:
                crear_backup(ruta, carpeta)
            except (OSError, sqlite3.Error) as e:
                app.logger.error(f"Falló el backup diario: {e}")
                return
        app.config["_ULTIMO_BACKUP"] = hoy