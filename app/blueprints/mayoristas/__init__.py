from flask import Blueprint

bp = Blueprint("mayoristas", __name__, url_prefix="/mayoristas")

from . import routes  # noqa: E402,F401