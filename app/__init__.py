import os
from flask import Flask
from config import Config
from .extensions import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # BD y archivos subidos viven en /instance (ignorado por Git)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "valery.db")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)

    from . import models  # noqa: F401  (registra los modelos para las migraciones)

    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.deudas import bp as deudas_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(deudas_bp)

    @app.template_filter("pesos")
    def pesos(valor):
        return "$" + f"{int(valor or 0):,}".replace(",", ".")

    return app