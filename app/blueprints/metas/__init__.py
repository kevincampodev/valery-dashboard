from flask import Blueprint

bp = Blueprint("metas", __name__, url_prefix="/metas")

from . import routes  # noqa: E402,F401