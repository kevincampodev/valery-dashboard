from flask import Blueprint

bp = Blueprint("deudas", __name__, url_prefix="/deudas")

from . import routes  # noqa: E402,F401