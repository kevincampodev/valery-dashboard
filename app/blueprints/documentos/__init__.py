from flask import Blueprint

bp = Blueprint("documentos", __name__, url_prefix="/documentos")

from . import routes  # noqa: E402,F401