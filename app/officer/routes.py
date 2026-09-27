import os
import json
from datetime import datetime, timezone, date, timedelta
from flask import (render_template, redirect, url_for, flash, request, abort,
                   current_app)
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.officer import officer
from app.models.user import User, Role
from app.models.claim import Claim, ClaimStatusHistory
from app.models.service import ServiceCenter, Technician, ServiceAssignment
from app.models.support import Notification
from app.models.warranty import Warranty, ProductRegistration
from app.models.customer import Customer
from app.utils.helpers import send_notification, notify_admins, allowed_file, save_uploaded_file
from app.utils.audit import log_action


def officer_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.is_warranty_officer():
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────── OFFICER DASHBOARD ───────────────────────────────

@officer.route('/dashboard')
@login_required
@officer_required
def dashboard():
    today = date.today()

    # Stats
    pending_claims = Claim.query.filter_by(status='submitted').count()
    under_review = Claim.query.filter_by(status='under_review').count()
    approved_today = (Claim.query
                      .filter(Claim.status == 'approved',
                              func.date(Claim.updated_at) == today)
                      .count())
    assigned_today = (Claim.query
                      .filter(Claim.status == 'assigned',
                              func.date(Claim.updated_at) == today)
                      .count())
    total_pending = pending_claims + under_review

    # Technician stats
    total_technicians = Technician.query.count()
    available_technicians = Technician.query.filter_by(is_available=True).count()
    busy_technicians = (Technician.query
                        .join(ServiceAssignment, Technician.id == ServiceAssignment.technician_id)
                        .join(Claim, ServiceAssignment.claim_id == Claim.id)
                        .filter(Claim.status.in_(['assigned', 'in_repair']))
                        .distinct().count())

    # Recent technicians list
    recent_technicians = (Technician.query
                          .order_by(Technician.created_at.desc())
                          .limit(5).all())

    # Recent pending claims (newest first)
    recent_pending = (Claim.query
                      .filter(Claim.status.in_(['submitted', 'under_review']))
                      .order_by(Claim.submitted_at.desc())
                      .limit(8)
                      .all())

    # Unread notifications
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    recent_notifications = (Notification.query
                            .filter_by(user_id=current_user.id)
                            .order_by(Notification.created_at.desc())
                            .limit(5)
                            .all())

    # Recently completed assignments
    completed_assignments = (ServiceAssignment.query
                             .filter_by(status='completed')
                             .order_by(ServiceAssignment.completed_at.desc())
                             .limit(5)
                             .all())

    return render_template('officer/dashboard.html',
                           total_pending=total_pending,
                           pending_claims=pending_claims,
                           under_review=under_review,
                           approved_today=approved_today,
                           assigned_today=assigned_today,
                           recent_pending=recent_pending,
                           unread_count=unread_count,
                           recent_notifications=recent_notifications,
                           completed_assignments=completed_assignments,
                           total_technicians=total_technicians,
                           available_technicians=available_technicians,
                           busy_technicians=busy_technicians,
                           recent_technicians=recent_technicians,
                           title='Officer Dashboard')


# ─────────────────────────── REQUESTS LIST ───────────────────────────────────

@officer.route('/requests')
@login_required
@officer_required
def requests():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'pending')
    search = request.args.get('search', '').strip()

    if status_filter == 'pending':
        status_values = ['submitted', 'under_review']
    elif status_filter == 'approved':
        status_values = ['approved', 'assigned', 'in_repair', 'completed', 'closed']
    elif status_filter == 'rejected':
        status_values = ['rejected']
    else:
        status_values = list(Claim.STATUS_LABELS.keys())

    query = Claim.query.join(Customer, Claim.customer_id == Customer.id)
    query = query.filter(Claim.status.in_(status_values))

    if search:
        query = query.filter(Customer.full_name.ilike(f'%{search}%'))

    pagination = query.order_by(Claim.submitted_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template('officer/requests.html',
                           claims=pagination.items,
                           pagination=pagination,
                           status_filter=status_filter,
                           search=search,
                           title='Warranty Requests')


# ─────────────────────────── REQUEST DETAIL ──────────────────────────────────

@officer.route('/requests/<int:claim_id>')
@login_required
@officer_required
def request_detail(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    history = claim.status_history.order_by(ClaimStatusHistory.changed_at.asc()).all()

    # If still 'submitted', mark as under_review
    if claim.status == 'submitted':
        old_status = claim.status
        claim.status = 'under_review'
        claim.updated_at = datetime.now(timezone.utc)
        hist = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=old_status,
            new_status='under_review',
            changed_by_id=current_user.id,
            notes='Officer opened for review.'
        )
        db.session.add(hist)
        db.session.commit()

    service_centers = ServiceCenter.query.filter_by(is_active=True).all()
    technicians = Technician.query.filter_by(is_available=True).all()

    tech_data = {}
    for t in technicians:
        if t.service_center_id not in tech_data:
            tech_data[t.service_center_id] = []
        tech_data[t.service_center_id].append({
            'id': t.id,
            'name': t.full_name,
            'specialization': t.specialization or 'General'
        })
    technicians_json = json.dumps(tech_data)

    return render_template('officer/request_detail.html',
                           claim=claim,
                           history=history,
                           service_centers=service_centers,
                           technicians=technicians,
                           technicians_json=technicians_json,
                           title=f'Request #{claim.id}')


# ─────────────────────────── APPROVE ─────────────────────────────────────────

@officer.route('/requests/<int:claim_id>/approve', methods=['POST'])
@login_required
@officer_required
def approve_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)

    if claim.status not in ('submitted', 'under_review'):
        flash('This claim cannot be approved in its current state.', 'warning')
        return redirect(url_for('officer.request_detail', claim_id=claim_id))

    notes = request.form.get('notes', '').strip()
    old_status = claim.status
    claim.status = 'approved'
    claim.officer_notes = notes or None
    claim.updated_at = datetime.now(timezone.utc)

    hist = ClaimStatusHistory(
        claim_id=claim.id,
        old_status=old_status,
        new_status='approved',
        changed_by_id=current_user.id,
        notes=notes or 'Approved by officer.'
    )
    db.session.add(hist)
    db.session.commit()  # Commit approval first — notifications are secondary

    log_action('claim_approved', target_table='claims', target_id=claim.id,
               details=f'Officer approved claim #{claim.id}')

    # Safely build product description for notifications
    try:
        product_desc = (f'{claim.warranty.registration.product_model.product.brand} '
                        f'{claim.warranty.registration.product_model.model_name}')
    except AttributeError:
        product_desc = f'Claim #{claim.id}'

    # Notify customer
    try:
        customer_user = claim.customer.user
        send_notification(
            user_id=customer_user.id,
            title='✅ Claim Approved!',
            message=(f'Your claim #{claim.id} for {product_desc} '
                     f'has been approved. It will be assigned to a technician shortly.'),
            link=url_for('warranty.claim_detail', claim_id=claim.id),
            notification_type='claim_approved'
        )
    except Exception:
        pass  # Notification failure must not roll back the approval

    # Notify admins
    try:
        notify_admins(
            title=f'Officer Approved Claim #{claim.id}',
            message=(f'Officer {current_user.email} approved claim #{claim.id} '
                     f'from customer {claim.customer.full_name}.'),
            link=url_for('admin.claim_detail', claim_id=claim.id),
            notification_type='claim_approved'
        )
    except Exception:
        pass

    flash(f'Claim #{claim.id} has been approved. Now assign it to a technician.', 'success')
    # Redirect to the dedicated assignment page so officer can immediately assign
    return redirect(url_for('officer.assign_page', claim_id=claim_id))


# ─────────────────────────── REJECT ──────────────────────────────────────────

@officer.route('/requests/<int:claim_id>/reject', methods=['POST'])
@login_required
@officer_required
def reject_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)

    if claim.status not in ('submitted', 'under_review'):
        flash('This claim cannot be rejected in its current state.', 'warning')
        return redirect(url_for('officer.request_detail', claim_id=claim_id))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('A rejection reason is required.', 'danger')
        return redirect(url_for('officer.request_detail', claim_id=claim_id))

    old_status = claim.status
    claim.status = 'rejected'
    claim.officer_notes = reason
    claim.updated_at = datetime.now(timezone.utc)

    hist = ClaimStatusHistory(
        claim_id=claim.id,
        old_status=old_status,
        new_status='rejected',
        changed_by_id=current_user.id,
        notes=reason
    )
    db.session.add(hist)
    db.session.commit()  # Commit rejection first — notifications are secondary

    log_action('claim_rejected', target_table='claims', target_id=claim.id,
               details=f'Officer rejected claim #{claim.id}. Reason: {reason}')

    # Notify customer
    try:
        customer_user = claim.customer.user
        send_notification(
            user_id=customer_user.id,
            title='❌ Claim Rejected',
            message=(f'Your claim #{claim.id} has been rejected. Reason: {reason}'),
            link=url_for('warranty.claim_detail', claim_id=claim.id),
            notification_type='claim_rejected'
        )
    except Exception:
        pass  # Notification failure must not roll back the rejection

    # Notify admins
    try:
        notify_admins(
            title=f'Officer Rejected Claim #{claim.id}',
            message=(f'Officer {current_user.email} rejected claim #{claim.id} '
                     f'from customer {claim.customer.full_name}. Reason: {reason}'),
            link=url_for('admin.claim_detail', claim_id=claim.id),
            notification_type='claim_rejected'
        )
    except Exception:
        pass

    flash(f'Claim #{claim.id} has been rejected.', 'info')
    return redirect(url_for('officer.requests'))


# ─────────────────────────── ASSIGN PAGE (GET) ───────────────────────────────

@officer.route('/requests/<int:claim_id>/assign-page')
@login_required
@officer_required
def assign_page(claim_id):
    """Dedicated page shown after a claim is approved, to assign to a technician."""
    claim = Claim.query.get_or_404(claim_id)

    if claim.status not in ('approved',):
        # If already assigned, go to detail
        return redirect(url_for('officer.request_detail', claim_id=claim_id))

    service_centers = ServiceCenter.query.filter_by(is_active=True).all()
    technicians = Technician.query.filter_by(is_available=True).all()

    tech_data = {}
    for t in technicians:
        if t.service_center_id not in tech_data:
            tech_data[t.service_center_id] = []
        tech_data[t.service_center_id].append({
            'id': t.id,
            'name': t.full_name,
            'specialization': t.specialization or 'General'
        })
    technicians_json = json.dumps(tech_data)

    return render_template('officer/assign_page.html',
                           claim=claim,
                           service_centers=service_centers,
                           technicians=technicians,
                           technicians_json=technicians_json,
                           title=f'Assign Claim #{claim.id}')


# ─────────────────────────── ASSIGN TO TECHNICIAN ────────────────────────────

@officer.route('/requests/<int:claim_id>/assign', methods=['POST'])
@login_required
@officer_required
def assign_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != 'approved':
        flash('Only approved claims can be assigned to technicians.', 'warning')
        return redirect(url_for('officer.request_detail', claim_id=claim_id))

    service_center_id = request.form.get('service_center_id', type=int)
    technician_id = request.form.get('technician_id', type=int)
    due_date_str = request.form.get('due_date', '').strip()
    notes = request.form.get('assignment_notes', '').strip()

    if not service_center_id or not technician_id:
        flash('Please select both a service center and a technician.', 'danger')
        return redirect(url_for('officer.assign_page', claim_id=claim_id))

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Remove old assignment if exists
    if claim.service_assignment:
        db.session.delete(claim.service_assignment)
        db.session.flush()

    assignment = ServiceAssignment(
        claim_id=claim.id,
        technician_id=technician_id,
        service_center_id=service_center_id,
        due_date=due_date,
        notes=notes or None,
        status='pending'
    )
    db.session.add(assignment)

    old_status = claim.status
    claim.status = 'assigned'
    claim.updated_at = datetime.now(timezone.utc)

    hist = ClaimStatusHistory(
        claim_id=claim.id,
        old_status=old_status,
        new_status='assigned',
        changed_by_id=current_user.id,
        notes=f'Assigned to technician ID {technician_id}.'
    )
    db.session.add(hist)
    db.session.commit()  # Commit assignment first

    log_action('claim_assigned', target_table='service_assignments',
               target_id=assignment.id,
               details=f'Claim #{claim.id} assigned to technician #{technician_id}')

    # Safely build product description
    try:
        product_desc = (f'{claim.warranty.registration.product_model.product.brand} '
                        f'{claim.warranty.registration.product_model.model_name}')
    except AttributeError:
        product_desc = f'Claim #{claim.id}'

    # Notify technician
    try:
        tech = Technician.query.get(technician_id)
        if tech and tech.user_id:
            send_notification(
                user_id=tech.user_id,
                title=f'🔧 New Assignment: Claim #{claim.id}',
                message=(f'You have been assigned claim #{claim.id} for {product_desc}. '
                         f'Due: {due_date.strftime("%B %d, %Y") if due_date else "Not specified"}.'),
                link=url_for('admin.technician_dashboard'),
                notification_type='assigned'
            )
    except Exception:
        tech = None

    # Notify admins
    try:
        notify_admins(
            title=f'Claim #{claim.id} Assigned to Technician',
            message=(f'Officer {current_user.email} assigned claim #{claim.id} '
                     f'to technician {tech.full_name if tech else "Unknown"}.'),
            link=url_for('admin.claim_detail', claim_id=claim.id),
            notification_type='assigned'
        )
    except Exception:
        pass

    flash(f'Claim #{claim.id} has been assigned to a technician successfully! They have been notified.', 'success')
    return redirect(url_for('officer.request_detail', claim_id=claim_id))


# ─────────────────────────── OFFICER NOTIFICATIONS ───────────────────────────

@officer.route('/notifications')
@login_required
@officer_required
def notifications():
    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    all_notifications = (Notification.query
                         .filter_by(user_id=current_user.id)
                         .order_by(Notification.created_at.desc())
                         .all())

    return render_template('officer/notifications.html',
                           notifications=all_notifications,
                           title='My Notifications')


# ─────────────────────────── OFFICER PROFILE ─────────────────────────────────

@officer.route('/profile', methods=['GET', 'POST'])
@login_required
@officer_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        if full_name:
            current_user.full_name = full_name

        # Handle profile photo
        photo = request.files.get('profile_photo')
        if photo and photo.filename:
            if allowed_file(photo.filename):
                saved_path = save_uploaded_file(photo, subfolder='profiles')
                current_user.profile_photo = saved_path
            else:
                flash('Invalid file type. Please upload a PNG, JPG, or JPEG.', 'danger')
                return redirect(url_for('officer.profile'))

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('officer.profile'))

    return render_template('officer/profile.html', title='My Profile')


# ─────────────────────── OFFICER TECHNICIAN MANAGEMENT ───────────────────────

@officer.route('/technicians')
@login_required
@officer_required
def technicians():
    """List all technicians with their availability and active job counts."""
    from app.models.service import ServiceCenter
    from sqlalchemy import func as sqlfunc

    all_techs = (Technician.query
                 .join(ServiceCenter, Technician.service_center_id == ServiceCenter.id)
                 .order_by(Technician.full_name)
                 .all())

    # Active jobs per technician
    active_jobs_map = {}
    for tech in all_techs:
        count = (db.session.query(func.count(ServiceAssignment.id))
                 .join(Claim, ServiceAssignment.claim_id == Claim.id)
                 .filter(ServiceAssignment.technician_id == tech.id,
                         Claim.status.in_(['assigned', 'in_repair']))
                 .scalar()) or 0
        active_jobs_map[tech.id] = count

    total = len(all_techs)
    available = sum(1 for t in all_techs if t.is_available)

    return render_template('officer/technicians.html',
                           technicians=all_techs,
                           active_jobs_map=active_jobs_map,
                           total=total,
                           available=available,
                           title='Technicians')


@officer.route('/technicians/add', methods=['GET', 'POST'])
@login_required
@officer_required
def add_technician():
    """Officer adds a new technician — creates user account + technician profile."""
    from app.models.service import ServiceCenter
    from app.models.user import Role as RoleModel

    centers = ServiceCenter.query.filter_by(is_active=True).order_by(ServiceCenter.name).all()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        specialization = request.form.get('specialization', '').strip()
        phone = request.form.get('phone', '').strip()
        service_center_id = request.form.get('service_center_id', type=int)

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not email:
            errors.append('Email is required.')
        elif User.query.filter_by(email=email).first():
            errors.append(f'An account with email {email} already exists.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if not service_center_id:
            errors.append('Please select a service center.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('officer/add_technician.html',
                                   centers=centers, title='Add Technician')

        # Create user account
        tech_role = RoleModel.query.filter_by(name='technician').first()
        user = User(email=email, role_id=tech_role.id, is_active=True, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Create technician profile
        tech = Technician(
            user_id=user.id,
            service_center_id=service_center_id,
            full_name=full_name,
            specialization=specialization or None,
            phone=phone or None,
            is_available=True
        )
        db.session.add(tech)
        db.session.commit()

        log_action('technician_created', target_table='technicians',
                   target_id=tech.id,
                   details=f'Officer {current_user.email} added technician: {full_name} ({email})')

        # Notify admins
        notify_admins(
            title=f'🔧 New Technician Added by Officer',
            message=(f'Officer {current_user.full_name or current_user.email} added '
                     f'technician {full_name} ({email}).'),
            link=url_for('admin.technicians'),
            notification_type='technician_added'
        )

        flash(f'Technician {full_name} added successfully! Login: {email}', 'success')
        return redirect(url_for('officer.technicians'))

    return render_template('officer/add_technician.html',
                           centers=centers, title='Add Technician')
