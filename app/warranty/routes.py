from datetime import datetime, timezone
from flask import (render_template, redirect, url_for, flash, request, abort,
                   current_app)
from flask_login import login_required, current_user
from app import db
from app.warranty import warranty
from app.warranty.forms import ProductRegistrationForm, ClaimSubmissionForm, FeedbackForm
from app.models.product import ProductModel, WarrantyPolicy
from app.models.warranty import ProductRegistration, Invoice, Warranty
from app.models.claim import Claim, ClaimDocument, ClaimStatusHistory
from app.models.support import Notification
from app.models.user import Role
from app.utils.decorators import customer_required
from app.utils.helpers import (allowed_file, save_uploaded_file,
                               calculate_warranty_end_date, send_notification,
                               notify_admins, notify_officers, paginate_query)
from app.utils.audit import log_action


@warranty.route('/dashboard')
@login_required
@customer_required
def dashboard():
    customer = current_user.customer_profile
    if not customer:
        flash('Customer profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    # Get all warranties and update their expiry status
    warranties = (Warranty.query
                  .join(ProductRegistration)
                  .filter(ProductRegistration.customer_id == customer.id)
                  .all())

    for w in warranties:
        w.check_and_update_status()

    # Stats
    total_warranties = len(warranties)
    active_warranties = sum(1 for w in warranties if w.status == 'active')
    expired_warranties = sum(1 for w in warranties if w.status == 'expired')

    total_claims = customer.claims.count()
    open_claims = customer.claims.filter(
        Claim.status.notin_(['completed', 'closed', 'rejected'])
    ).count()

    # Expiry alerts
    expiring_soon = [w for w in warranties if w.is_expiring_soon and w.status == 'active']

    # Recent claims (last 5)
    recent_claims = (customer.claims
                     .order_by(Claim.submitted_at.desc())
                     .limit(5)
                     .all())

    # Unread notifications
    unread_notifications = (Notification.query
                            .filter_by(user_id=current_user.id, is_read=False)
                            .order_by(Notification.created_at.desc())
                            .limit(3)
                            .all())

    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()

    return render_template('customer/dashboard.html',
                           customer=customer,
                           total_warranties=total_warranties,
                           active_warranties=active_warranties,
                           expired_warranties=expired_warranties,
                           total_claims=total_claims,
                           open_claims=open_claims,
                           expiring_soon=expiring_soon,
                           recent_claims=recent_claims,
                           unread_notifications=unread_notifications,
                           unread_count=unread_count,
                           title='My Dashboard')


@warranty.route('/warranties')
@login_required
@customer_required
def warranties():
    customer = current_user.customer_profile
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)

    query = (Warranty.query
             .join(ProductRegistration)
             .filter(ProductRegistration.customer_id == customer.id))

    if status_filter in ('active', 'expired', 'voided'):
        query = query.filter(Warranty.status == status_filter)

    pagination = query.order_by(Warranty.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    warranty_list = pagination.items
    for w in warranty_list:
        w.check_and_update_status()

    return render_template('customer/warranties.html',
                           warranties=warranty_list,
                           pagination=pagination,
                           status_filter=status_filter,
                           title='My Warranties')


@warranty.route('/warranties/<int:warranty_id>')
@login_required
@customer_required
def warranty_detail(warranty_id):
    customer = current_user.customer_profile
    w = Warranty.query.get_or_404(warranty_id)

    # Verify ownership
    if w.registration.customer_id != customer.id:
        abort(403)

    w.check_and_update_status()
    claims = w.claims.order_by(Claim.submitted_at.desc()).all()

    return render_template('customer/warranty_detail.html',
                           warranty=w,
                           claims=claims,
                           title='Warranty Details')


@warranty.route('/register', methods=['GET', 'POST'])
@login_required
@customer_required
def register_product():
    customer = current_user.customer_profile
    form = ProductRegistrationForm()

    # Populate choices
    models = ProductModel.query.filter_by(is_active=True).all()
    form.product_model_id.choices = [
        (m.id, f'{m.product.brand} - {m.model_name} ({m.model_number})')
        for m in models
    ]

    if form.validate_on_submit():
        # Double-check serial number uniqueness (business rule enforcement)
        existing = ProductRegistration.query.filter_by(
            serial_number=form.serial_number.data.strip()
        ).first()
        if existing:
            flash('This serial number is already registered.', 'danger')
            return render_template('customer/register_product.html', form=form,
                                   title='Register Product')

        product_model = ProductModel.query.get(form.product_model_id.data)
        if not product_model:
            flash('Invalid product model selected.', 'danger')
            return render_template('customer/register_product.html', form=form,
                                   title='Register Product')

        # Create registration
        registration = ProductRegistration(
            customer_id=customer.id,
            product_model_id=product_model.id,
            serial_number=form.serial_number.data.strip(),
            purchase_date=form.purchase_date.data,
            retailer_name=form.retailer_name.data.strip() if form.retailer_name.data else None,
            notes=form.notes.data.strip() if form.notes.data else None
        )
        db.session.add(registration)
        db.session.flush()

        # Save invoice if uploaded
        if form.invoice_file.data and form.invoice_file.data.filename:
            file = form.invoice_file.data
            if allowed_file(file.filename):
                saved_path = save_uploaded_file(file, subfolder='invoices')
                invoice = Invoice(
                    registration_id=registration.id,
                    file_path=saved_path,
                    original_filename=file.filename
                )
                db.session.add(invoice)

        # Calculate warranty end date
        end_date = calculate_warranty_end_date(
            form.purchase_date.data,
            product_model.warranty_period_months
        )

        # Find active policy for model
        policy = WarrantyPolicy.query.filter_by(
            product_model_id=product_model.id,
            is_active=True
        ).first()

        # Create warranty
        w = Warranty(
            registration_id=registration.id,
            policy_id=policy.id if policy else None,
            start_date=form.purchase_date.data,
            end_date=end_date,
            status='active'
        )
        db.session.add(w)
        db.session.commit()

        log_action('product_registered', target_table='product_registrations',
                   target_id=registration.id,
                   details=f'SN: {registration.serial_number}')

        # Send notification to customer
        send_notification(
            user_id=current_user.id,
            title='Product Registered Successfully',
            message=(f'Your {product_model.product.brand} {product_model.model_name} has been '
                     f'registered. Warranty valid until {end_date.strftime("%B %d, %Y")}.'),
            link=url_for('warranty.warranty_detail', warranty_id=w.id),
            notification_type='registration'
        )

        # Notify officers about new registration
        notify_officers(
            title=f'📦 New Product Registered by {customer.full_name}',
            message=(f'Customer {customer.full_name} registered '
                     f'{product_model.product.brand} {product_model.model_name} '
                     f'(SN: {registration.serial_number}).'),
            link=url_for('admin.warranties'),
            notification_type='registration'
        )

        # Notify admins
        notify_admins(
            title=f'New Product Registration by {customer.full_name}',
            message=(f'Customer {customer.full_name} registered '
                     f'{product_model.product.brand} {product_model.model_name} '
                     f'(SN: {registration.serial_number}).'),
            link=url_for('admin.warranties'),
            notification_type='registration'
        )

        flash(f'Product registered successfully! Warranty valid until {end_date.strftime("%B %d, %Y")}.', 'success')
        return redirect(url_for('warranty.warranties'))

    return render_template('customer/register_product.html', form=form, title='Register Product')


@warranty.route('/claims')
@login_required
@customer_required
def claims():
    customer = current_user.customer_profile
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)

    query = customer.claims
    if status_filter == 'open':
        query = query.filter(Claim.status.notin_(['completed', 'closed', 'rejected']))
    elif status_filter == 'resolved':
        query = query.filter(Claim.status.in_(['completed', 'closed', 'rejected']))

    pagination = query.order_by(Claim.submitted_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    return render_template('customer/claims.html',
                           claims=pagination.items,
                           pagination=pagination,
                           status_filter=status_filter,
                           title='My Claims')


@warranty.route('/claims/<int:claim_id>')
@login_required
@customer_required
def claim_detail(claim_id):
    customer = current_user.customer_profile
    claim = Claim.query.get_or_404(claim_id)

    if claim.customer_id != customer.id:
        abort(403)

    history = claim.status_history.order_by(ClaimStatusHistory.changed_at.asc()).all()

    return render_template('customer/claim_detail.html',
                           claim=claim,
                           history=history,
                           title=f'Claim #{claim.id}')


@warranty.route('/claims/submit/<int:warranty_id>', methods=['GET', 'POST'])
@login_required
@customer_required
def submit_claim(warranty_id):
    customer = current_user.customer_profile
    w = Warranty.query.get_or_404(warranty_id)

    # Verify ownership
    if w.registration.customer_id != customer.id:
        abort(403)

    # Check if warranty is active
    w.check_and_update_status()
    if not w.is_active:
        flash(f'This warranty expired on {w.end_date.strftime("%B %d, %Y")} and is no longer eligible for claims.', 'danger')
        return redirect(url_for('warranty.warranty_detail', warranty_id=warranty_id))

    form = ClaimSubmissionForm()
    form.warranty_id.data = warranty_id

    if form.validate_on_submit():
        claim = Claim(
            warranty_id=w.id,
            customer_id=customer.id,
            claim_type=form.claim_type.data,
            description=form.description.data.strip(),
            status='submitted'
        )
        db.session.add(claim)
        db.session.flush()

        # Save attachments
        for file in request.files.getlist('attachments'):
            if file and file.filename and allowed_file(file.filename):
                saved_path = save_uploaded_file(file, subfolder='claim_docs')
                ext = file.filename.rsplit('.', 1)[-1].lower()
                doc = ClaimDocument(
                    claim_id=claim.id,
                    file_path=saved_path,
                    original_filename=file.filename,
                    file_type=ext
                )
                db.session.add(doc)

        # Create status history
        history = ClaimStatusHistory(
            claim_id=claim.id,
            old_status=None,
            new_status='submitted',
            changed_by_id=current_user.id,
            notes='Claim submitted by customer.'
        )
        db.session.add(history)
        db.session.commit()

        log_action('claim_submitted', target_table='claims', target_id=claim.id,
                   details=f'Customer {customer.full_name} submitted claim for warranty #{w.id}')

        # Notify all warranty officers
        notify_officers(
            title='🆕 New Warranty Claim Submitted',
            message=(f'New claim #{claim.id} submitted by {customer.full_name} for '
                     f'{w.registration.product_model.product.brand} '
                     f'{w.registration.product_model.model_name}.'),
            link=url_for('officer.request_detail', claim_id=claim.id),
            notification_type='claim_submitted'
        )

        # Notify admins
        notify_admins(
            title=f'New Claim Submitted by {customer.full_name}',
            message=(f'Customer {customer.full_name} submitted a warranty claim for '
                     f'{w.registration.product_model.product.brand} '
                     f'{w.registration.product_model.model_name}.'),
            link=url_for('admin.claim_detail', claim_id=claim.id),
            notification_type='claim_submitted'
        )

        flash('Your claim has been submitted successfully! We will review it shortly.', 'success')
        return redirect(url_for('warranty.claims'))

    return render_template('customer/submit_claim.html',
                           form=form,
                           warranty=w,
                           title='Submit Warranty Claim')


@warranty.route('/notifications')
@login_required
def notifications():
    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    all_notifications = (Notification.query
                         .filter_by(user_id=current_user.id)
                         .order_by(Notification.created_at.desc())
                         .all())

    return render_template('customer/notifications.html',
                           notifications=all_notifications,
                           title='Notifications')


@warranty.route('/feedback/<int:claim_id>', methods=['GET', 'POST'])
@login_required
@customer_required
def feedback(claim_id):
    customer = current_user.customer_profile
    claim = Claim.query.get_or_404(claim_id)

    if claim.customer_id != customer.id:
        abort(403)

    if claim.status not in ('completed', 'closed'):
        flash('Feedback can only be submitted for completed or closed claims.', 'warning')
        return redirect(url_for('warranty.claim_detail', claim_id=claim_id))

    if claim.feedback:
        flash('You have already submitted feedback for this claim.', 'info')
        return redirect(url_for('warranty.claim_detail', claim_id=claim_id))

    form = FeedbackForm()
    if form.validate_on_submit():
        from app.models.support import Feedback as FeedbackModel
        fb = FeedbackModel(
            claim_id=claim.id,
            customer_id=customer.id,
            rating=int(form.rating.data),
            comments=form.comments.data.strip() if form.comments.data else None
        )
        db.session.add(fb)
        db.session.commit()
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('warranty.claim_detail', claim_id=claim_id))

    return render_template('customer/feedback.html',
                           form=form,
                           claim=claim,
                           title='Submit Feedback')
