import os

from flask import Flask, flash, redirect, request, url_for
from flask_wtf.csrf import CSRFError
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import db, migrate, csrf, login_manager, limiter
from .utils import formato_pesos, formato_bp, formato_tamano


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    if app.config.get("ENTORNO") == "produccion":
        clave = app.config.get("SECRET_KEY") or ""
        if len(clave) < 32 or clave.startswith("dev"):
            raise RuntimeError("SECRET_KEY insegura: en producción define una clave larga y aleatoria en .env")
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    from .encabezados import registrar_encabezados
    registrar_encabezados(app)

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
    login_manager.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def cargar_usuario(id_sesion):
        from .models import Usuario
        try:
            usuario_id, version = (int(parte) for parte in id_sesion.split("-"))
        except ValueError:
            return None
        usuario = db.session.get(Usuario, usuario_id)
        if usuario and usuario.activo and usuario.version_sesion == version:
            return usuario
        return None

    from . import models  # noqa: F401  (registra los modelos para las migraciones)
    from .services.auditoria import activar_auditoria
    from .services.backups import registrar_backup_diario
    activar_auditoria()
    registrar_backup_diario(app)

    # Módulos
    from .blueprints import (auth, dashboard, deudas, abonos, ventas, mayoristas, metas, comisiones,
                             proyecciones, pagos, marketing, documentos, reportes, sistema)
    for modulo in (auth, dashboard, deudas, abonos, ventas, mayoristas, metas, comisiones,
                   proyecciones, pagos, marketing, documentos, reportes, sistema):
        app.register_blueprint(modulo.bp)

    # Candado global: nada se ve sin iniciar sesión
    PUBLICAS = {"auth.login", "auth.verificar", "static"}
    PERMITIDAS_SIN_CONFIGURAR = {"auth.cuenta", "auth.cambiar_password", "auth.activar_2fa", "auth.logout", "static"}

    @app.before_request
    def exigir_sesion():
        if request.endpoint in PUBLICAS:
            return None
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        cuenta_incompleta = current_user.debe_cambiar_password or not current_user.totp_activo
        if cuenta_incompleta and request.endpoint not in PERMITIDAS_SIN_CONFIGURAR:
            return redirect(url_for("auth.cuenta"))
        return None

    from .cli import (seed_demo, importar_ventas, reclasificar_canal,
                      crear_usuario, reiniciar_2fa, desbloquear_usuario, desactivar_usuario)
    for comando in (seed_demo, importar_ventas, reclasificar_canal,
                    crear_usuario, reiniciar_2fa, desbloquear_usuario, desactivar_usuario):
        app.cli.add_command(comando)

    # Filtros de plantilla
    app.add_template_filter(formato_pesos, "pesos")
    app.add_template_filter(formato_bp, "porcentaje")
    app.add_template_filter(formato_tamano, "tamano")

    @app.errorhandler(CSRFError)
    def csrf_invalido(error):
        flash("El formulario expiró o no es válido. Intenta de nuevo.", "warning")
        return redirect(request.referrer or url_for("dashboard.index"))

    return app