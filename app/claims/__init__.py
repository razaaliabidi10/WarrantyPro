from flask import Blueprint

claims = Blueprint('claims', __name__)

from app.claims import routes  # noqa: F401, E402
