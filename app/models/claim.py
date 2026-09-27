from datetime import datetime, timezone
from app import db


class Claim(db.Model):
    __tablename__ = 'claims'

    STATUS_LABELS = {
        'submitted': ('Submitted', 'warning'),
        'under_review': ('Under Review', 'info'),
        'approved': ('Approved', 'success'),
        'rejected': ('Rejected', 'danger'),
        'assigned': ('Assigned', 'primary'),
        'in_repair': ('In Repair', 'secondary'),
        'ready': ('Ready for Pickup', 'success'),
        'completed': ('Completed', 'success'),
        'closed': ('Closed', 'dark'),
    }

    id = db.Column(db.Integer, primary_key=True)
    warranty_id = db.Column(db.Integer, db.ForeignKey('warranties.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    claim_type = db.Column(db.String(50), nullable=False)  # hardware_defect, physical_damage, software_issue, other
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default='submitted', nullable=False)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    officer_notes = db.Column(db.Text, nullable=True)

    # Relationships
    documents = db.relationship('ClaimDocument', backref='claim', lazy='dynamic')
    status_history = db.relationship('ClaimStatusHistory', backref='claim', lazy='dynamic',
                                     order_by='ClaimStatusHistory.changed_at')
    service_assignment = db.relationship('ServiceAssignment', backref='claim', uselist=False, lazy='select')
    replacement = db.relationship('ReplacementRecord', backref='claim', uselist=False, lazy='select')
    refund = db.relationship('Refund', backref='claim', uselist=False, lazy='select')
    feedback = db.relationship('Feedback', backref='claim', uselist=False, lazy='select')

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, (self.status, 'secondary'))

    def __repr__(self):
        return f'<Claim #{self.id} status={self.status}>'


class ClaimDocument(db.Model):
    __tablename__ = 'claim_documents'

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ClaimDocument {self.original_filename}>'


class ClaimStatusHistory(db.Model):
    __tablename__ = 'claim_status_history'

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.id'), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    changed_by = db.relationship('User', foreign_keys=[changed_by_id])

    def __repr__(self):
        return f'<ClaimStatusHistory {self.old_status}→{self.new_status}>'
