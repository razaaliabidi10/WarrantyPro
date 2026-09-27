import json
from datetime import datetime, timezone, date, timedelta
from flask import (render_template, redirect, url_for, flash, request, abort,
                   jsonify, send_from_directory, current_app)
from flask_login import login_required, current_user
from sqlalchemy import func, extract, and_
from app import db
from app.admin import admin
from app.models.user import User, Role
from app.models.customer import Customer
from app.models.product import Product, ProductModel, WarrantyPolicy
from app.models.warranty import ProductRegistration, Warranty
from app.models.claim import Claim, ClaimStatusHistory
from app.models.service import (ServiceCenter, Technician, ServiceAssignment,
                                 Inspection, Repair, RepairPart)
from app.models.support import AuditLog, Notification
from app.utils.decorators import admin_required, warranty_officer_required, technician_required
from app.utils.helpers import send_notification, notify_admins, allowed_file, save_uploaded_file
from app.utils.audit import log_action


def officer_or_admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if not (current_user.is_admin() or current_user.is_warranty_officer()):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────── ADMIN DASHBOARD ──────────────────────────────

@admin.route('/dashboard')
@login_required
@officer_or_admin_required
def dashboard():
    today = date.today()

    # KPI stats
    total_registrations = ProductRegistration.query.count()
    active_warranties = Warranty.query.filter_by(status='active').count()

    expiring_soon = (Warranty.query
                     .filter(Warranty.status == 'active',
                             Warranty.end_date <= today + timedelta(days=30),
                             Warranty.end_date >= today)
                     .count())

    total_claims = Claim.query.count()
    pending_review = Claim.query.filter_by(status='under_review').count()

    # Claims resolved today
    resolved_today = (Claim.query
                      .filter(Claim.status.in_(['completed', 'closed']),
                              func.date(Claim.updated_at) == today)
                      .count())

    # Claims by status for doughnut chart
    status_counts = (db.session.query(Claim.status, func.count(Claim.id))
                     .group_by(Claim.status)
                     .all())
    chart_status = {s: c for s, c in status_counts}

    # Claims per month last 6 months
    six_months_ago = today.replace(day=1) - timedelta(days=150)
    monthly_data = (db.session.query(
        extract('year', Claim.submitted_at).label('yr'),
        extract('month', Claim.submitted_at).label('mo'),
        func.count(Claim.id)
    )
        .filter(Claim.submitted_at >= six_months_ago)
        .group_by('yr', 'mo')
        .order_by('yr', 'mo')
        .all())

    months_labels = []
    months_data = []
    for yr, mo, cnt in monthly_data:
        months_labels.append(f"{int(mo):02d}/{int(yr)}")
        months_data.append(cnt)

    # Recent claims
    recent_claims = (Claim.query
                     .order_by(Claim.submitted_at.desc())
                     .limit(30)
                     .all())

    # Recent audit logs
    recent_audits = (AuditLog.query
                     .order_by(AuditLog.timestamp.desc())
                     .limit(30)
                     .all())

    # Recent admin notifications (activity feed)
    recent_notifications = (Notification.query
                            .filter_by(user_id=current_user.id)
                            .order_by(Notification.created_at.desc())
                            .limit(15)
                            .all())
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

    return render_template('admin/dashboard.html',
                           total_registrations=total_registrations,
                           active_warranties=active_warranties,
                           expiring_soon=expiring_soon,
                           total_claims=total_claims,
                           pending_review=pending_review,
                           resolved_today=resolved_today,
                           chart_status=json.dumps(chart_status),
                           months_labels=json.dumps(months_labels),
                           months_data=json.dumps(months_data),
                           recent_claims=recent_claims,
                           recent_audits=recent_audits,
                           recent_notifications=recent_notifications,
                           unread_count=unread_count,
                           title='Admin Dashboard')


@admin.route('/notifications')
@login_required
@admin_required
def notifications():
    """Admin notification inbox — sees all system events."""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    all_notifications = (Notification.query
                         .filter_by(user_id=current_user.id)
                         .order_by(Notification.created_at.desc())
                         .all())
    return render_template('admin/notifications.html',
                           notifications=all_notifications,
                           title='Activity Feed')


@admin.route('/profile', methods=['GET', 'POST'])
@login_required
@admin_required
def profile():
    from app.utils.helpers import allowed_file, save_uploaded_file
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        if full_name:
            current_user.full_name = full_name

        # Admin-only: update email
        new_email = request.form.get('email', '').strip().lower()
        if new_email and new_email != current_user.email:
            existing = User.query.filter(
                User.email == new_email, User.id != current_user.id
            ).first()
            if existing:
                flash('That email address is already in use.', 'danger')
                return redirect(url_for('admin.profile'))
            current_user.email = new_email

        # Admin-only: update phone (stored on admin's customer/technician profile if present)
        new_phone = request.form.get('phone', '').strip()
        if new_phone is not None:
            # Store on whichever sub-profile exists, else ignore gracefully
            if current_user.customer_profile:
                current_user.customer_profile.phone = new_phone or None
            # No sub-profile? We still save it — silently ignore

        photo = request.files.get('profile_photo')
        if photo and photo.filename:
            if allowed_file(photo.filename):
                saved_path = save_uploaded_file(photo, subfolder='profiles')
                current_user.profile_photo = saved_path
            else:
                flash('Invalid file type. Please upload PNG, JPG, or JPEG.', 'danger')
                return redirect(url_for('admin.profile'))
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('admin.profile'))
    return render_template('shared/profile.html', title='My Profile')


# ──────────────────────────── CLAIMS MANAGEMENT ─────────────────────────────


@admin.route('/claims')
@login_required
@officer_or_admin_required
def claims():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('claim_type', '')
    search = request.args.get('search', '').strip()

    query = Claim.query.join(Customer, Claim.customer_id == Customer.id)

    if status_filter:
        query = query.filter(Claim.status == status_filter)
    if type_filter:
        query = query.filter(Claim.claim_type == type_filter)
    if search:
        query = query.filter(Customer.full_name.ilike(f'%{search}%'))

    pagination = query.order_by(Claim.submitted_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    return render_template('admin/claims.html',
                           claims=pagination.items,
                           pagination=pagination,
                           status_filter=status_filter,
                           type_filter=type_filter,
                           search=search,
                           all_statuses=list(Claim.STATUS_LABELS.keys()),
                           title='All Claims')


@admin.route('/claims/<int:claim_id>', methods=['GET', 'POST'])
@login_required
@officer_or_admin_required
def claim_detail(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    history = claim.status_history.order_by(ClaimStatusHistory.changed_at.asc()).all()

    if request.method == 'POST':
        new_status = request.form.get('new_status')
        notes = request.form.get('notes', '').strip()

        valid_statuses = list(Claim.STATUS_LABELS.keys())
        if new_status not in valid_statuses:
            flash('Invalid status selected.', 'danger')
            return redirect(url_for('admin.claim_detail', claim_id=claim_id))

        old_status = claim.status

        # Create history record
        hist = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=old_status,
            new_status=new_status,
            changed_by_id=current_user.id,
            notes=notes or None
        )
        db.session.add(hist)

        # Update claim
        claim.status = new_status
        claim.updated_at = datetime.now(timezone.utc)
        if new_status == 'rejected' and notes:
            claim.officer_notes = notes

        db.session.commit()

        log_action('claim_status_updated', target_table='claims', target_id=claim.id,
                   details=f'Status changed from {old_status} to {new_status}')

        # Notify customer
        customer_user = claim.customer.user
        if new_status == 'approved':
            send_notification(
                user_id=customer_user.id,
                title='Claim Approved',
                message=f'Your claim #{claim.id} has been approved and will be assigned for service.',
                link=url_for('warranty.claim_detail', claim_id=claim.id)
            )
        elif new_status == 'rejected':
            send_notification(
                user_id=customer_user.id,
                title='Claim Rejected',
                message=f'Your claim #{claim.id} has been rejected. Reason: {notes}',
                link=url_for('warranty.claim_detail', claim_id=claim.id)
            )

        flash(f'Claim status updated to {new_status.replace("_", " ").title()}.', 'success')
        return redirect(url_for('admin.claim_detail', claim_id=claim_id))

    service_centers = ServiceCenter.query.filter_by(is_active=True).all()
    technicians = Technician.query.filter_by(is_available=True).all()

    import json
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

    return render_template('admin/claim_detail.html',
                           claim=claim,
                           history=history,
                           service_centers=service_centers,
                           technicians=technicians,
                           technicians_json=technicians_json,
                           all_statuses=Claim.STATUS_LABELS,
                           title=f'Claim #{claim.id}')


@admin.route('/claims/<int:claim_id>/assign', methods=['POST'])
@login_required
@officer_or_admin_required
def assign_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)

    service_center_id = request.form.get('service_center_id', type=int)
    technician_id = request.form.get('technician_id', type=int)
    due_date_str = request.form.get('due_date', '').strip()
    notes = request.form.get('notes', '').strip()

    if not service_center_id or not technician_id:
        flash('Please select both a service center and technician.', 'danger')
        return redirect(url_for('admin.claim_detail', claim_id=claim_id))

    # Parse due date
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
        notes=notes or None
    )
    db.session.add(assignment)

    # Update claim status
    old_status = claim.status
    claim.status = 'assigned'
    claim.updated_at = datetime.now(timezone.utc)

    hist = ClaimStatusHistory(
        claim_id=claim.id,
        old_status=old_status,
        new_status='assigned',
        changed_by_id=current_user.id,
        notes=f'Assigned to technician #{technician_id}'
    )
    db.session.add(hist)
    db.session.commit()

    # Notify technician
    tech = Technician.query.get(technician_id)
    if tech and tech.user:
        send_notification(
            user_id=tech.user_id,
            title=f'New Assignment: Claim #{claim.id}',
            message=(f'You have been assigned claim #{claim.id} for '
                     f'{claim.warranty.registration.product_model.product.brand} '
                     f'{claim.warranty.registration.product_model.model_name}. '
                     f'Due: {due_date.strftime("%B %d, %Y") if due_date else "Not specified"}.'),
            link=url_for('admin.assignment_detail', assignment_id=assignment.id)
        )

    log_action('claim_assigned', target_table='service_assignments', target_id=assignment.id,
               details=f'Claim #{claim.id} assigned to technician #{technician_id}')
    flash('Claim assigned to technician successfully.', 'success')
    return redirect(url_for('admin.claim_detail', claim_id=claim_id))


# ─────────────────────────── WARRANTIES LIST ────────────────────────────────

@admin.route('/warranties')
@login_required
@officer_or_admin_required
def warranties():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '').strip()

    query = (Warranty.query
             .join(ProductRegistration, Warranty.registration_id == ProductRegistration.id)
             .join(Customer, ProductRegistration.customer_id == Customer.id))

    if status_filter:
        query = query.filter(Warranty.status == status_filter)
    if search:
        query = query.filter(
            db.or_(
                ProductRegistration.serial_number.ilike(f'%{search}%'),
                Customer.full_name.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(Warranty.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    return render_template('admin/warranties.html',
                           warranties=pagination.items,
                           pagination=pagination,
                           status_filter=status_filter,
                           search=search,
                           title='All Warranties')


# ────────────────────────── PRODUCTS MANAGEMENT ─────────────────────────────

@admin.route('/products')
@login_required
@admin_required
def products():
    all_products = ProductModel.query.join(Product).order_by(Product.brand).all()
    return render_template('admin/products.html', products=all_products, title='Products')


@admin.route('/products/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        step = request.form.get('step', '1')

        if step == '1':
            # Create product
            brand = request.form.get('brand', '').strip()
            category = request.form.get('category', '').strip()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()

            if not brand or not category or not name:
                flash('Brand, category, and product name are required.', 'danger')
                return render_template('admin/add_product.html', step=1, title='Add Product')

            product = Product(brand=brand, category=category, name=name,
                              description=description or None)
            db.session.add(product)
            db.session.commit()
            log_action('product_created', target_table='products', target_id=product.id,
                       details=f'Product: {brand} {name}')
            flash('Product created! Now add a model.', 'info')
            return render_template('admin/add_product.html', step=2, product=product,
                                   title='Add Product Model')

        elif step == '2':
            product_id = request.form.get('product_id', type=int)
            model_name = request.form.get('model_name', '').strip()
            model_number = request.form.get('model_number', '').strip()
            warranty_months = request.form.get('warranty_period_months', 12, type=int)

            if not model_name or not model_number:
                flash('Model name and model number are required.', 'danger')
                product = Product.query.get(product_id)
                return render_template('admin/add_product.html', step=2, product=product,
                                       title='Add Product Model')

            existing = ProductModel.query.filter_by(model_number=model_number).first()
            if existing:
                flash(f'Model number {model_number} is already registered.', 'danger')
                product = Product.query.get(product_id)
                return render_template('admin/add_product.html', step=2, product=product,
                                       title='Add Product Model')

            model = ProductModel(
                product_id=product_id,
                model_name=model_name,
                model_number=model_number,
                warranty_period_months=warranty_months
            )
            db.session.add(model)
            db.session.commit()
            log_action('product_model_created', target_table='product_models',
                       target_id=model.id, details=f'Model: {model_name} ({model_number})')
            flash('Product model added! Now define the warranty policy.', 'info')
            return render_template('admin/add_product.html', step=3, model=model,
                                   title='Add Warranty Policy')

        elif step == '3':
            model_id = request.form.get('model_id', type=int)
            policy_name = request.form.get('policy_name', '').strip()
            coverage_details = request.form.get('coverage_details', '').strip()
            exclusions = request.form.get('exclusions', '').strip()
            terms = request.form.get('terms', '').strip()

            if not policy_name:
                flash('Policy name is required.', 'danger')
                model = ProductModel.query.get(model_id)
                return render_template('admin/add_product.html', step=3, model=model,
                                       title='Add Warranty Policy')

            policy = WarrantyPolicy(
                product_model_id=model_id,
                policy_name=policy_name,
                coverage_details=coverage_details or None,
                exclusions=exclusions or None,
                terms=terms or None
            )
            db.session.add(policy)
            db.session.commit()
            log_action('warranty_policy_created', target_table='warranty_policies',
                       target_id=policy.id, details=f'Policy: {policy_name}')
            flash('Product, model, and warranty policy created successfully!', 'success')
            return redirect(url_for('admin.products'))

    return render_template('admin/add_product.html', step=1, title='Add Product')


# ──────────────────────── SERVICE CENTERS & TECHNICIANS ─────────────────────

@admin.route('/service-centers', methods=['GET', 'POST'])
@login_required
@admin_required
def service_centers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()

        if not name:
            flash('Service center name is required.', 'danger')
        else:
            center = ServiceCenter(
                name=name, address=address or None, city=city or None,
                phone=phone or None, email=email or None
            )
            db.session.add(center)
            db.session.commit()
            log_action('service_center_created', target_table='service_centers',
                       target_id=center.id, details=f'Center: {name}')
            flash(f'Service center "{name}" added successfully.', 'success')
        return redirect(url_for('admin.service_centers'))

    centers = ServiceCenter.query.order_by(ServiceCenter.name).all()
    return render_template('admin/service_centers.html', centers=centers,
                           title='Service Centers')


@admin.route('/technicians', methods=['GET', 'POST'])
@login_required
@admin_required
def technicians():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        specialization = request.form.get('specialization', '').strip()
        service_center_id = request.form.get('service_center_id', type=int)
        phone = request.form.get('phone', '').strip()

        if not full_name or not email or not service_center_id:
            flash('Full name, email, and service center are required.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash(f'A user with email {email} already exists.', 'danger')
        else:
            tech_role = Role.query.filter_by(name='technician').first()
            user = User(email=email, role_id=tech_role.id, is_active=True)
            user.set_password('raza@8521')
            db.session.add(user)
            db.session.flush()

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
                       target_id=tech.id, details=f'Technician: {full_name}')
            flash(f'Technician {full_name} added with login email {email}.', 'success')
        return redirect(url_for('admin.technicians'))

    all_techs = (Technician.query
                 .join(ServiceCenter)
                 .order_by(Technician.full_name)
                 .all())
    centers = ServiceCenter.query.filter_by(is_active=True).order_by(ServiceCenter.name).all()

    # Compute active job counts per technician (ServiceAssignment has no status; use Claim status)
    active_jobs_map = {}
    for tech in all_techs:
        count = (db.session.query(func.count(ServiceAssignment.id))
                 .join(Claim, ServiceAssignment.claim_id == Claim.id)
                 .filter(ServiceAssignment.technician_id == tech.id,
                         Claim.status.in_(['assigned', 'in_repair']))
                 .scalar()) or 0
        active_jobs_map[tech.id] = count

    return render_template('admin/technicians.html', technicians=all_techs,
                           centers=centers, active_jobs_map=active_jobs_map,
                           title='Technicians')


# ──────────────────────────── USERS MANAGEMENT ──────────────────────────────

@admin.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    all_users = (User.query
                 .order_by(User.created_at.desc())
                 .paginate(page=page, per_page=20, error_out=False))
    return render_template('admin/users.html', users=all_users.items,
                           pagination=all_users, title='Users')


@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    action = 'activated' if user.is_active else 'deactivated'
    log_action(f'user_{action}', target_table='users', target_id=user.id,
               details=f'User {user.email} was {action}')
    flash(f'User {user.email} has been {action}.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.order_by(Role.name).all()

    if request.method == 'POST':
        # Prevent admin from changing their own role (lockout guard)
        if user.id != current_user.id:
            new_role_id = request.form.get('role_id', type=int)
            if new_role_id:
                new_role = Role.query.get(new_role_id)
                if new_role:
                    user.role_id = new_role.id

            # Update active status (unchecked checkbox sends nothing)
            user.is_active = bool(request.form.get('is_active'))

        db.session.commit()
        log_action('user_edited', target_table='users', target_id=user.id,
                   details=f'Admin edited user {user.email}')
        flash(f'User {user.email} updated successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/edit_user.html', user=user, roles=roles,
                           title=f'Edit User – {user.email}')


# ──────────────────────────── REPORTS ───────────────────────────────────────

@admin.route('/reports')
@login_required
@admin_required
def reports():
    from datetime import date, timedelta

    # Report 1: Warranty registrations for last 30 days (date → count)
    thirty_days_ago = date.today() - timedelta(days=29)
    reg_data = (
        db.session.query(
            func.date(ProductRegistration.created_at).label('reg_date'),
            func.count(ProductRegistration.id)
        )
        .filter(func.date(ProductRegistration.created_at) >= thirty_days_ago)
        .group_by(func.date(ProductRegistration.created_at))
        .order_by(func.date(ProductRegistration.created_at))
        .all()
    )
    # Build a full date range so the chart has no gaps
    daily_registrations = {}
    for i in range(30):
        d = (thirty_days_ago + timedelta(days=i)).strftime('%m/%d')
        daily_registrations[d] = 0
    for reg_date, cnt in reg_data:
        if hasattr(reg_date, 'strftime'):
            key = reg_date.strftime('%m/%d')
        else:
            from datetime import datetime as dt_
            key = dt_.strptime(str(reg_date), '%Y-%m-%d').strftime('%m/%d')
        if key in daily_registrations:
            daily_registrations[key] = cnt

    # Report 2: Claim counts by status
    status_counts = (
        db.session.query(Claim.status, func.count(Claim.id))
        .group_by(Claim.status)
        .all()
    )
    claim_status_counts = {s: c for s, c in status_counts}

    # Report 3: Technician performance
    tech_rows = (
        db.session.query(
            Technician.full_name,
            ServiceCenter.name.label('center'),
            func.count(ServiceAssignment.id).label('total_jobs'),
            func.sum(
                db.case((Claim.status.in_(['completed', 'closed']), 1), else_=0)
            ).label('completed')
        )
        .join(ServiceCenter, Technician.service_center_id == ServiceCenter.id)
        .outerjoin(ServiceAssignment, Technician.id == ServiceAssignment.technician_id)
        .outerjoin(Claim, ServiceAssignment.claim_id == Claim.id)
        .group_by(Technician.id, Technician.full_name, ServiceCenter.name)
        .order_by(func.count(ServiceAssignment.id).desc())
        .all()
    )
    tech_perf = [
        {
            'name': row.full_name,
            'center': row.center,
            'total_jobs': row.total_jobs or 0,
            'completed': int(row.completed or 0),
            'rating': 0  # Rating system not implemented yet
        }
        for row in tech_rows
    ]

    return render_template('admin/reports.html',
                           daily_registrations=json.dumps(daily_registrations),
                           claim_status_counts=json.dumps(claim_status_counts),
                           tech_perf=tech_perf,
                           title='Reports')


# ──────────────────────────── AUDIT LOGS ────────────────────────────────────

@admin.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    user_filter = request.args.get('user_id', type=int)
    keyword = request.args.get('keyword', '').strip()

    query = AuditLog.query
    if user_filter:
        query = query.filter_by(user_id=user_filter)
    if keyword:
        query = query.filter(AuditLog.action.ilike(f'%{keyword}%'))

    pagination = query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    all_users = User.query.order_by(User.email).all()

    return render_template('admin/audit_logs.html',
                           logs=pagination.items,
                           pagination=pagination,
                           all_users=all_users,
                           user_filter=user_filter,
                           keyword=keyword,
                           title='Audit Logs')


# ──────────────────── TECHNICIAN VIEWS ──────────────────────────────────────

@admin.route('/technician-dashboard')
@login_required
def technician_dashboard():
    if not (current_user.is_technician() or current_user.is_admin()):
        abort(403)

    tech = current_user.technician_profile
    if not tech and not current_user.is_admin():
        flash('Technician profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    if current_user.is_admin():
        # Admin seeing technician dashboard — show all
        assignments = ServiceAssignment.query.order_by(ServiceAssignment.assigned_at.desc()).limit(20).all()
        total_assigned = ServiceAssignment.query.count()
        in_progress = Claim.query.filter_by(status='in_repair').count()
        completed_month = (Claim.query
                           .filter(Claim.status.in_(['completed', 'closed']),
                                   extract('month', Claim.updated_at) == date.today().month)
                           .count())
    else:
        assignments = tech.assignments.order_by(ServiceAssignment.assigned_at.desc()).all()
        total_assigned = tech.assignments.count()
        in_progress = (tech.assignments
                       .join(Claim, ServiceAssignment.claim_id == Claim.id)
                       .filter(Claim.status == 'in_repair')
                       .count())
        completed_month = (tech.assignments
                           .join(Claim, ServiceAssignment.claim_id == Claim.id)
                           .filter(Claim.status.in_(['completed', 'closed']),
                                   extract('month', Claim.updated_at) == date.today().month)
                           .count())

    return render_template('admin/technician_dashboard.html',
                           assignments=assignments,
                           total_assigned=total_assigned,
                           in_progress=in_progress,
                           completed_month=completed_month,
                           title='Technician Dashboard')


@admin.route('/assignments/<int:assignment_id>/update-status', methods=['POST'])
@login_required
def update_assignment_status(assignment_id):
    """Technician updates their work status: start or complete."""
    if not (current_user.is_technician() or current_user.is_admin()):
        abort(403)

    assignment = ServiceAssignment.query.get_or_404(assignment_id)

    # Technicians can only update their own assignments
    if current_user.is_technician():
        tech = current_user.technician_profile
        if tech and assignment.technician_id != tech.id:
            abort(403)

    action = request.form.get('action', '')
    tech_notes = request.form.get('technician_notes', '').strip()
    claim = assignment.claim

    if action == 'start':
        assignment.status = 'in_progress'
        assignment.started_at = datetime.now(timezone.utc)
        if tech_notes:
            assignment.technician_notes = tech_notes

        old_status = claim.status
        claim.status = 'in_repair'
        claim.updated_at = datetime.now(timezone.utc)
        hist = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=old_status,
            new_status='in_repair',
            changed_by_id=current_user.id,
            notes='Technician started working on the product.'
        )
        db.session.add(hist)
        db.session.commit()

        # Notify officers — link to officer.request_detail so they can see it
        try:
            officer_role = Role.query.filter_by(name='warranty_officer').first()
            if officer_role:
                officers = User.query.filter_by(role_id=officer_role.id, is_active=True).all()
                for off in officers:
                    send_notification(
                        user_id=off.id,
                        title=f'🔧 Technician Started Work: Claim #{claim.id}',
                        message=f'Technician {assignment.technician.full_name} has started work on claim #{claim.id}.',
                        link=url_for('officer.request_detail', claim_id=claim.id),
                        notification_type='technician_update'
                    )
        except Exception:
            pass
        try:
            notify_admins(
                title=f'Technician Started Work on Claim #{claim.id}',
                message=f'Technician {assignment.technician.full_name} started working on claim #{claim.id}.',
                link=url_for('admin.claim_detail', claim_id=claim.id),
                notification_type='technician_update'
            )
        except Exception:
            pass
        flash('Work started! Officers have been notified.', 'success')

    elif action == 'complete':
        assignment.status = 'completed'
        assignment.completed_at = datetime.now(timezone.utc)
        if tech_notes:
            assignment.technician_notes = tech_notes

        old_status = claim.status
        claim.status = 'ready'
        claim.updated_at = datetime.now(timezone.utc)
        hist = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=old_status,
            new_status='ready',
            changed_by_id=current_user.id,
            notes=f'Technician completed work. Notes: {tech_notes or "None"}'
        )
        db.session.add(hist)

        # Make technician available again
        if current_user.is_technician():
            t = current_user.technician_profile
            if t:
                t.is_available = True

        db.session.commit()

        # Notify officers — link to officer.request_detail so officers can view the completed claim
        try:
            officer_role = Role.query.filter_by(name='warranty_officer').first()
            if officer_role:
                officers = User.query.filter_by(role_id=officer_role.id, is_active=True).all()
                for off in officers:
                    send_notification(
                        user_id=off.id,
                        title=f'✅ Technician Completed Work: Claim #{claim.id}',
                        message=(f'Technician {assignment.technician.full_name} completed work on '
                                 f'claim #{claim.id}. Product is ready for pickup.'),
                        link=url_for('officer.request_detail', claim_id=claim.id),
                        notification_type='technician_update'
                    )
        except Exception:
            pass
        try:
            notify_admins(
                title=f'Technician Completed Claim #{claim.id}',
                message=(f'Technician {assignment.technician.full_name} completed work on '
                         f'claim #{claim.id}. Product is ready for pickup.'),
                link=url_for('admin.claim_detail', claim_id=claim.id),
                notification_type='technician_update'
            )
        except Exception:
            pass
        flash('✅ Work marked as complete! Officers and admin have been notified.', 'success')

    else:
        flash('Invalid action.', 'danger')

    return redirect(url_for('admin.technician_dashboard'))


@admin.route('/assignments/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def assignment_detail(assignment_id):
    if not (current_user.is_technician() or current_user.is_admin() or
            current_user.is_warranty_officer()):
        abort(403)

    assignment = ServiceAssignment.query.get_or_404(assignment_id)

    # Technicians can only see their own assignments
    if current_user.is_technician():
        tech = current_user.technician_profile
        if tech and assignment.technician_id != tech.id:
            abort(403)

    if request.method == 'POST' and not assignment.inspection:
        findings = request.form.get('findings', '').strip()
        diagnosis = request.form.get('diagnosis', '').strip()
        recommended_action = request.form.get('recommended_action', '').strip()

        inspection = Inspection(
            assignment_id=assignment.id,
            findings=findings or None,
            diagnosis=diagnosis or None,
            recommended_action=recommended_action or None
        )
        db.session.add(inspection)

        # Update claim status
        claim = assignment.claim
        old_status = claim.status
        claim.status = 'in_repair'
        claim.updated_at = datetime.now(timezone.utc)

        hist = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=old_status,
            new_status='in_repair',
            changed_by_id=current_user.id,
            notes='Inspection completed. Repair in progress.'
        )
        db.session.add(hist)
        db.session.commit()

        # Notify warranty officers
        officer_role = Role.query.filter_by(name='warranty_officer').first()
        if officer_role:
            officers = User.query.filter_by(role_id=officer_role.id, is_active=True).all()
            for off in officers:
                send_notification(
                    user_id=off.id,
                    title=f'Inspection Complete: Claim #{claim.id}',
                    message=f'Technician has completed inspection for claim #{claim.id}. Recommended: {recommended_action}.',
                    link=url_for('admin.claim_detail', claim_id=claim.id)
                )

        log_action('inspection_submitted', target_table='inspections',
                   target_id=inspection.id,
                   details=f'Claim #{claim.id}: {recommended_action}')
        flash('Inspection submitted. Repair started.', 'success')
        return redirect(url_for('admin.assignment_detail', assignment_id=assignment_id))

    return render_template('admin/assignment_detail.html',
                           assignment=assignment,
                           title=f'Assignment #{assignment.id}')


@admin.route('/assignments/<int:assignment_id>/repair', methods=['POST'])
@login_required
def update_repair(assignment_id):
    if not (current_user.is_technician() or current_user.is_admin()):
        abort(403)

    assignment = ServiceAssignment.query.get_or_404(assignment_id)

    if current_user.is_technician():
        tech = current_user.technician_profile
        if tech and assignment.technician_id != tech.id:
            abort(403)

    action = request.form.get('action', '')
    inspection = assignment.inspection

    if not inspection:
        flash('No inspection found for this assignment.', 'danger')
        return redirect(url_for('admin.assignment_detail', assignment_id=assignment_id))

    if action == 'add_part':
        part_name = request.form.get('part_name', '').strip()
        part_number = request.form.get('part_number', '').strip()
        quantity = request.form.get('quantity', 1, type=int)
        unit_cost_str = request.form.get('unit_cost', '0').strip()

        if part_name:
            try:
                unit_cost = float(unit_cost_str)
            except ValueError:
                unit_cost = 0.0

            if not inspection.repair:
                repair = Repair(inspection_id=inspection.id, status='in_progress',
                                started_at=datetime.now(timezone.utc))
                db.session.add(repair)
                db.session.flush()
            else:
                repair = inspection.repair

            part = RepairPart(
                repair_id=repair.id,
                part_name=part_name,
                part_number=part_number or None,
                quantity=quantity,
                unit_cost=unit_cost
            )
            db.session.add(part)
            db.session.commit()
            flash('Part added successfully.', 'success')

    elif action == 'complete_repair':
        repair_notes = request.form.get('repair_notes', '').strip()
        if not inspection.repair:
            repair = Repair(inspection_id=inspection.id, status='completed',
                            started_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc),
                            notes=repair_notes or None)
            db.session.add(repair)
        else:
            repair = inspection.repair
            repair.status = 'completed'
            repair.completed_at = datetime.now(timezone.utc)
            repair.notes = repair_notes or None

        # Calculate total cost
        if inspection.repair:
            parts = inspection.repair.parts.all()
            total = sum((p.unit_cost or 0) * p.quantity for p in parts)
            repair.total_cost = total

        # Update claim status
        claim = assignment.claim
        old_status = claim.status
        claim.status = 'ready'
        claim.updated_at = datetime.now(timezone.utc)

        hist = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=old_status,
            new_status='ready',
            changed_by_id=current_user.id,
            notes='Repair completed. Ready for pickup.'
        )
        db.session.add(hist)

        # Mark technician as available again
        if current_user.is_technician():
            tech = current_user.technician_profile
            if tech:
                tech.is_available = True

        db.session.commit()

        # Notify customer
        customer_user = claim.customer.user
        service_center = assignment.service_center
        send_notification(
            user_id=customer_user.id,
            title='Your Product is Ready for Pickup',
            message=(f'Your product is ready for pickup at '
                     f'{service_center.name}, {service_center.city}.'),
            link=url_for('warranty.claim_detail', claim_id=claim.id)
        )

        log_action('repair_completed', target_table='repairs', target_id=repair.id,
                   details=f'Claim #{claim.id} repair completed.')
        flash('Repair marked as complete. Customer has been notified.', 'success')

    return redirect(url_for('admin.assignment_detail', assignment_id=assignment_id))
