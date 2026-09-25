from flask import Blueprint

bp = Blueprint("ventas", __name__, url_prefix="/ventas")

from . import routes  # noqa: E402,F401