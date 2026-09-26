from flask import Blueprint

bp = Blueprint("proyecciones", __name__, url_prefix="/proyecciones")

from . import routes  # noqa: E402,F401