from flask import Blueprint

bp = Blueprint("comisiones", __name__, url_prefix="/comisiones")

from . import routes  # noqa: E402,F401