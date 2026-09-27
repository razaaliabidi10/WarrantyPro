from functools import wraps
from flask import abort
from flask_login import current_user


def admin_required(f):
    """Abort 403 if current user is not an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def warranty_officer_required(f):
    """Abort 403 if current user is not a warranty_officer or admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if not (current_user.is_warranty_officer() or current_user.is_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def technician_required(f):
    """Abort 403 if current user is not a technician."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_technician():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def customer_required(f):
    """Abort 403 if current user is not a customer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_customer():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def dealer_required(f):
    """Abort 403 if current user is not a dealer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_dealer():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
