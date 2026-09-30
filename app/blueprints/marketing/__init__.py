from flask import Blueprint

bp = Blueprint("marketing", __name__, url_prefix="/publicidad")

from . import routes  # noqa: E402,F401