from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from app.main import main
from app import db
from app.utils.helpers import allowed_file, save_uploaded_file


@main.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_warranty_officer():
            return redirect(url_for('officer.dashboard'))
        elif current_user.is_technician():
            return redirect(url_for('admin.technician_dashboard'))
        else:
            return redirect(url_for('warranty.dashboard'))
    return render_template('main/index.html', title='Digital Warranty Management')


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Universal profile page for customers and technicians."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        if full_name:
            current_user.full_name = full_name
            # Also update role-specific profile name
            if current_user.is_customer() and current_user.customer_profile:
                current_user.customer_profile.full_name = full_name
            elif current_user.is_technician() and current_user.technician_profile:
                current_user.technician_profile.full_name = full_name

        photo = request.files.get('profile_photo')
        if photo and photo.filename:
            if allowed_file(photo.filename):
                saved_path = save_uploaded_file(photo, subfolder='profiles')
                current_user.profile_photo = saved_path
            else:
                flash('Invalid file type. Use PNG, JPG, or JPEG.', 'danger')
                return redirect(url_for('main.profile'))

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))

    return render_template('shared/profile.html', title='My Profile')


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('shared/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('shared/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('shared/500.html'), 500
