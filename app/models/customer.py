from datetime import datetime, timezone
from app import db


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    registrations = db.relationship('ProductRegistration', backref='customer', lazy='dynamic')
    claims = db.relationship('Claim', backref='customer', lazy='dynamic')
    feedbacks = db.relationship('Feedback', backref='customer', lazy='dynamic')
    complaints = db.relationship('Complaint', backref='customer', lazy='dynamic')

    def __repr__(self):
        return f'<Customer {self.full_name}>'


class Dealer(db.Model):
    __tablename__ = 'dealers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    business_name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    registrations = db.relationship('ProductRegistration', backref='dealer', lazy='dynamic',
                                    foreign_keys='ProductRegistration.dealer_id')

    def __repr__(self):
        return f'<Dealer {self.business_name}>'
