from flask import Blueprint

warranty = Blueprint('warranty', __name__)

from app.warranty import routes  # noqa: F401, E402
