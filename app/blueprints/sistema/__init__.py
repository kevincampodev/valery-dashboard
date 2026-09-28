from flask import Blueprint

bp = Blueprint("sistema", __name__, url_prefix="/sistema")

from . import routes  # noqa: E402,F401