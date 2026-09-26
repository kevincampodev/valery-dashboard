from flask import Blueprint

bp = Blueprint("pagos", __name__, url_prefix="/pagos-pendientes")

from . import routes  # noqa: E402,F401