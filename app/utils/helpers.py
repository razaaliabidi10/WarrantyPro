import os
import uuid
from datetime import date
from flask import current_app
from dateutil.relativedelta import relativedelta
from app import db


def allowed_file(filename):
    """Check if file extension is allowed."""
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, subfolder='general'):
    """Save uploaded file to uploads/subfolder with UUID prefix. Returns saved relative path."""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    target_dir = os.path.join(upload_folder, subfolder)
    os.makedirs(target_dir, exist_ok=True)

    original_filename = file.filename
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    unique_filename = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    save_path = os.path.join(target_dir, unique_filename)
    file.save(save_path)

    # Return relative path for storage
    return os.path.join(subfolder, unique_filename)


def calculate_warranty_end_date(purchase_date, months):
    """Calculate warranty end date from purchase date plus months."""
    if isinstance(purchase_date, date):
        end_date = purchase_date + relativedelta(months=months)
        return end_date
    return None


def send_notification(user_id, title, message, link=None, notification_type=None):
    """Create and save a Notification record for a user."""
    from app.models.support import Notification
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link,
        is_read=False,
        notification_type=notification_type
    )
    db.session.add(notification)
    db.session.commit()


def notify_admins(title, message, link=None, notification_type=None):
    """Send a notification copy to all active admin users."""
    from app.models.user import User, Role
    from app.models.support import Notification
    admin_role = Role.query.filter_by(name='admin').first()
    if not admin_role:
        return
    admins = User.query.filter_by(role_id=admin_role.id, is_active=True).all()
    for admin_user in admins:
        notif = Notification(
            user_id=admin_user.id,
            title=title,
            message=message,
            link=link,
            is_read=False,
            notification_type=notification_type
        )
        db.session.add(notif)
    db.session.commit()


def notify_officers(title, message, link=None, notification_type=None):
    """Send a notification copy to all active warranty officer users."""
    from app.models.user import User, Role
    from app.models.support import Notification
    officer_role = Role.query.filter_by(name='warranty_officer').first()
    if not officer_role:
        return
    officers = User.query.filter_by(role_id=officer_role.id, is_active=True).all()
    for off_user in officers:
        notif = Notification(
            user_id=off_user.id,
            title=title,
            message=message,
            link=link,
            is_read=False,
            notification_type=notification_type
        )
        db.session.add(notif)
    db.session.commit()


def paginate_query(query, page, per_page=10):
    """Return paginated results from a query."""
    return query.paginate(page=page, per_page=per_page, error_out=False)
