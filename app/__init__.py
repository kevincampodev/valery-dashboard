import os

from flask import Flask, flash, redirect, request, url_for
from flask_wtf.csrf import CSRFError

from config import Config
from .extensions import db, migrate, csrf
from .utils import formato_pesos, formato_bp, formato_tamano


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Rutas de datos: todo vive en /instance (ignorado por Git)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["DB_PATH"] = os.path.join(app.instance_path, app.config["DB_NAME"])
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + app.config["DB_PATH"]
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    es_principal = app.config["DB_NAME"] == "valery.db"
    carpeta_backups = "backups" if es_principal else f"backups-{os.path.splitext(app.config['DB_NAME'])[0]}"
    app.config["BACKUP_DIR"] = (app.config.get("BACKUP_DIR") if es_principal else None) \
        or os.path.join(app.instance_path, carpeta_backups)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registra los modelos para las migraciones)
    from .services.auditoria import activar_auditoria
    from .services.backups import registrar_backup_diario
    activar_auditoria()
    registrar_backup_diario(app)

    # Módulos
    from .blueprints import (dashboard, deudas, abonos, ventas, metas, comisiones,
                             proyecciones, pagos, documentos, reportes, sistema)
    for modulo in (dashboard, deudas, abonos, ventas, metas, comisiones,
                   proyecciones, pagos, documentos, reportes, sistema):
        app.register_blueprint(modulo.bp)

    from .cli import seed_demo, importar_ventas
    app.cli.add_command(seed_demo)
    app.cli.add_command(importar_ventas)

    # Filtros de plantilla
    app.add_template_filter(formato_pesos, "pesos")
    app.add_template_filter(formato_bp, "porcentaje")
    app.add_template_filter(formato_tamano, "tamano")

    @app.errorhandler(CSRFError)
    def csrf_invalido(error):
        flash("El formulario expiró o no es válido. Intenta de nuevo.", "warning")
        return redirect(request.referrer or url_for("dashboard.index"))

    return app