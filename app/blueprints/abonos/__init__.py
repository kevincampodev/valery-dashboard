from flask import Blueprint

bp = Blueprint("abonos", __name__, url_prefix="/abonos")

from . import routes  # noqa: E402,F401