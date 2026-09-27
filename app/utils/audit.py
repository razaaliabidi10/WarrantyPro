from datetime import datetime, timezone
from flask import request
from flask_login import current_user
from app import db


def log_action(action, target_table=None, target_id=None, details=None):
    """Create an AuditLog record for a sensitive action."""
    from app.models.support import AuditLog
    user_id = None
    if current_user and current_user.is_authenticated:
        user_id = current_user.id

    ip_address = None
    try:
        ip_address = request.remote_addr
    except RuntimeError:
        pass

    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        target_table=target_table,
        target_id=target_id,
        details=details,
        ip_address=ip_address,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(log_entry)
    db.session.commit()
