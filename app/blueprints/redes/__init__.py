from flask import Blueprint

bp = Blueprint("redes", __name__, url_prefix="/redes")

from . import routes  # noqa: E402,F401
