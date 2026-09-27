from datetime import date, timedelta
from flask import jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.api import api
from app.models.warranty import Warranty, ProductRegistration
from app.models.claim import Claim, ClaimStatusHistory
from app.models.support import Notification
from app.utils.decorators import admin_required


def error_response(message, code):
    return jsonify({'error': message, 'code': code}), code


# ──────────────────────── CUSTOMER WARRANTY API ──────────────────────────────

@api.route('/warranties')
@login_required
def get_warranties():
    if not current_user.is_customer():
        return error_response('Forbidden', 403)
    customer = current_user.customer_profile
    warranties = (Warranty.query
                  .join(ProductRegistration)
                  .filter(ProductRegistration.customer_id == customer.id)
                  .all())
    result = []
    for w in warranties:
        result.append({
            'id': w.id,
            'status': w.status,
            'start_date': str(w.start_date),
            'end_date': str(w.end_date),
            'days_remaining': w.days_remaining,
            'is_active': w.is_active,
            'product': f'{w.registration.product_model.product.brand} {w.registration.product_model.model_name}',
            'serial_number': w.registration.serial_number,
        })
    return jsonify(result)


@api.route('/warranties/<int:warranty_id>')
@login_required
def get_warranty(warranty_id):
    if not current_user.is_customer():
        return error_response('Forbidden', 403)
    customer = current_user.customer_profile
    w = Warranty.query.get_or_404(warranty_id)
    if w.registration.customer_id != customer.id:
        return error_response('Forbidden', 403)
    return jsonify({
        'id': w.id,
        'status': w.status,
        'start_date': str(w.start_date),
        'end_date': str(w.end_date),
        'days_remaining': w.days_remaining,
        'is_active': w.is_active,
        'product': f'{w.registration.product_model.product.brand} {w.registration.product_model.model_name}',
        'serial_number': w.registration.serial_number,
        'policy': w.policy.policy_name if w.policy else None,
    })


# ────────────────────────── CUSTOMER CLAIM API ───────────────────────────────

@api.route('/claims')
@login_required
def get_claims():
    if not current_user.is_customer():
        return error_response('Forbidden', 403)
    customer = current_user.customer_profile
    claims = customer.claims.order_by(Claim.submitted_at.desc()).all()
    result = []
    for c in claims:
        result.append({
            'id': c.id,
            'claim_type': c.claim_type,
            'status': c.status,
            'status_label': c.status_label[0],
            'submitted_at': c.submitted_at.isoformat(),
            'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        })
    return jsonify(result)


@api.route('/claims/<int:claim_id>')
@login_required
def get_claim(claim_id):
    if not current_user.is_customer():
        return error_response('Forbidden', 403)
    customer = current_user.customer_profile
    claim = Claim.query.get_or_404(claim_id)
    if claim.customer_id != customer.id:
        return error_response('Forbidden', 403)
    history = claim.status_history.order_by(ClaimStatusHistory.changed_at.asc()).all()
    return jsonify({
        'id': claim.id,
        'claim_type': claim.claim_type,
        'status': claim.status,
        'description': claim.description,
        'submitted_at': claim.submitted_at.isoformat(),
        'officer_notes': claim.officer_notes,
        'history': [
            {
                'from': h.old_status,
                'to': h.new_status,
                'at': h.changed_at.isoformat(),
                'notes': h.notes
            } for h in history
        ]
    })


# ─────────────────────────── NOTIFICATIONS API ───────────────────────────────

@api.route('/notifications')
@login_required
def get_notifications():
    notifications = (Notification.query
                     .filter_by(user_id=current_user.id, is_read=False)
                     .order_by(Notification.created_at.desc())
                     .all())
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'created_at': n.created_at.isoformat(),
        'link': n.link
    } for n in notifications])


@api.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    n = Notification.query.get_or_404(notification_id)
    if n.user_id != current_user.id:
        return error_response('Forbidden', 403)
    n.is_read = True
    db.session.commit()
    return jsonify({'success': True})


# ────────────────────────── ADMIN STATS API ──────────────────────────────────

@api.route('/admin/stats')
@login_required
@admin_required
def admin_stats():
    today = date.today()

    total_claims = Claim.query.count()
    active_warranties = Warranty.query.filter_by(status='active').count()
    expiring_soon = (Warranty.query
                     .filter(Warranty.status == 'active',
                             Warranty.end_date <= today + timedelta(days=30),
                             Warranty.end_date >= today)
                     .count())

    status_counts = (db.session.query(Claim.status, func.count(Claim.id))
                     .group_by(Claim.status).all())

    # Technicians by service center
    tech_by_center = {}
    from app.models.service import Technician, ServiceCenter
    centers = ServiceCenter.query.filter_by(is_active=True).all()
    for center in centers:
        techs = Technician.query.filter_by(
            service_center_id=center.id, is_available=True
        ).all()
        tech_by_center[center.id] = [{
            'id': t.id,
            'name': t.full_name,
            'specialization': t.specialization
        } for t in techs]

    return jsonify({
        'total_claims': total_claims,
        'active_warranties': active_warranties,
        'expiring_soon': expiring_soon,
        'claims_by_status': {s: c for s, c in status_counts},
        'technicians_by_center': tech_by_center,
    })
