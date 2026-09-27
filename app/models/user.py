from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    # Universal profile fields for ALL roles
    full_name = db.Column(db.String(150), nullable=True)
    profile_photo = db.Column(db.String(500), nullable=True)  # relative path to uploaded photo

    # Relationships
    customer_profile = db.relationship('Customer', backref='user', uselist=False, lazy='select')
    dealer_profile = db.relationship('Dealer', backref='user', uselist=False, lazy='select')
    technician_profile = db.relationship('Technician', backref='user', uselist=False, lazy='select')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic',
                                    foreign_keys='Notification.user_id')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic',
                                 foreign_keys='AuditLog.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, name):
        return self.role is not None and self.role.name == name

    def is_admin(self):
        return self.has_role('admin')

    def is_customer(self):
        return self.has_role('customer')

    def is_warranty_officer(self):
        return self.has_role('warranty_officer')

    def is_technician(self):
        return self.has_role('technician')

    def is_dealer(self):
        return self.has_role('dealer')

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.email}>'
