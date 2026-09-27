from datetime import datetime, date, timezone
from app import db


class ProductRegistration(db.Model):
    __tablename__ = 'product_registrations'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    product_model_id = db.Column(db.Integer, db.ForeignKey('product_models.id'), nullable=False)
    dealer_id = db.Column(db.Integer, db.ForeignKey('dealers.id'), nullable=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    retailer_name = db.Column(db.String(200), nullable=True)
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    invoices = db.relationship('Invoice', backref='registration', lazy='dynamic')
    warranty = db.relationship('Warranty', backref='registration', uselist=False, lazy='select')

    def __repr__(self):
        return f'<ProductRegistration SN:{self.serial_number}>'


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('product_registrations.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Invoice {self.original_filename}>'


class Warranty(db.Model):
    __tablename__ = 'warranties'

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('product_registrations.id'),
                                nullable=False, unique=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('warranty_policies.id'), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    policy = db.relationship('WarrantyPolicy', backref='warranties', lazy='select')
    claims = db.relationship('Claim', backref='warranty', lazy='dynamic')

    @property
    def is_active(self):
        if self.status == 'voided':
            return False
        today = date.today()
        return self.status == 'active' and self.end_date >= today

    @property
    def days_remaining(self):
        today = date.today()
        delta = (self.end_date - today).days
        return max(0, delta)

    @property
    def is_expiring_soon(self):
        return 0 < self.days_remaining <= 30

    def check_and_update_status(self):
        if self.status == 'active' and self.end_date < date.today():
            self.status = 'expired'
            db.session.commit()

    def __repr__(self):
        return f'<Warranty #{self.id} status={self.status}>'
