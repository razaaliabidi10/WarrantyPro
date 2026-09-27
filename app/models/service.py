from datetime import datetime, timezone
from app import db


class ServiceCenter(db.Model):
    __tablename__ = 'service_centers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    technicians = db.relationship('Technician', backref='service_center', lazy='dynamic')
    assignments = db.relationship('ServiceAssignment', backref='service_center', lazy='dynamic')

    def __repr__(self):
        return f'<ServiceCenter {self.name}>'


class Technician(db.Model):
    __tablename__ = 'technicians'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    service_center_id = db.Column(db.Integer, db.ForeignKey('service_centers.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    assignments = db.relationship('ServiceAssignment', backref='technician', lazy='dynamic')

    def __repr__(self):
        return f'<Technician {self.full_name}>'


class ServiceAssignment(db.Model):
    __tablename__ = 'service_assignments'

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.id'), nullable=False, unique=True)
    technician_id = db.Column(db.Integer, db.ForeignKey('technicians.id'), nullable=False)
    service_center_id = db.Column(db.Integer, db.ForeignKey('service_centers.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # Technician work status
    status = db.Column(db.String(30), default='pending', nullable=False)  # pending, in_progress, completed
    technician_notes = db.Column(db.Text, nullable=True)  # technician's work notes
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    inspection = db.relationship('Inspection', backref='assignment', uselist=False, lazy='select')

    def __repr__(self):
        return f'<ServiceAssignment claim_id={self.claim_id}>'


class Inspection(db.Model):
    __tablename__ = 'inspections'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('service_assignments.id'), nullable=False, unique=True)
    findings = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    photos_path = db.Column(db.String(500), nullable=True)
    inspected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    recommended_action = db.Column(db.String(50), nullable=True)  # repair, replace, refund, no_action

    # Relationships
    repair = db.relationship('Repair', backref='inspection', uselist=False, lazy='select')

    def __repr__(self):
        return f'<Inspection assignment_id={self.assignment_id}>'


class Repair(db.Model):
    __tablename__ = 'repairs'

    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspections.id'), nullable=False, unique=True)
    status = db.Column(db.String(30), default='pending', nullable=False)  # pending, in_progress, completed, failed
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    total_cost = db.Column(db.Numeric(10, 2), nullable=True)

    # Relationships
    parts = db.relationship('RepairPart', backref='repair', lazy='dynamic')

    def __repr__(self):
        return f'<Repair inspection_id={self.inspection_id} status={self.status}>'


class RepairPart(db.Model):
    __tablename__ = 'repair_parts'

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey('repairs.id'), nullable=False)
    part_name = db.Column(db.String(200), nullable=False)
    part_number = db.Column(db.String(100), nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=True)

    def __repr__(self):
        return f'<RepairPart {self.part_name}>'


class ReplacementRecord(db.Model):
    __tablename__ = 'replacement_records'

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.id'), nullable=False, unique=True)
    new_serial_number = db.Column(db.String(100), nullable=True)
    replacement_reason = db.Column(db.Text, nullable=True)
    authorized_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    replaced_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    authorized_by = db.relationship('User', foreign_keys=[authorized_by_id])

    def __repr__(self):
        return f'<ReplacementRecord claim_id={self.claim_id}>'


class Refund(db.Model):
    __tablename__ = 'refunds'

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.id'), nullable=False, unique=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    processed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    processed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, processed, failed

    # Relationships
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])

    def __repr__(self):
        return f'<Refund claim_id={self.claim_id} amount={self.amount}>'
