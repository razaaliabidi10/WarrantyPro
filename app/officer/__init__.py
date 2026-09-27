from flask import Blueprint

officer = Blueprint('officer', __name__)

from app.officer import routes  # noqa: F401, E402
