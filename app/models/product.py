from datetime import datetime, timezone
from app import db


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    models = db.relationship('ProductModel', backref='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.brand} - {self.name}>'


class ProductModel(db.Model):
    __tablename__ = 'product_models'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    model_name = db.Column(db.String(200), nullable=False)
    model_number = db.Column(db.String(100), unique=True, nullable=False)
    warranty_period_months = db.Column(db.Integer, default=12, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    warranty_policies = db.relationship('WarrantyPolicy', backref='product_model', lazy='dynamic')
    registrations = db.relationship('ProductRegistration', backref='product_model', lazy='dynamic')

    def __repr__(self):
        return f'<ProductModel {self.model_name} ({self.model_number})>'


class WarrantyPolicy(db.Model):
    __tablename__ = 'warranty_policies'

    id = db.Column(db.Integer, primary_key=True)
    product_model_id = db.Column(db.Integer, db.ForeignKey('product_models.id'), nullable=False)
    policy_name = db.Column(db.String(200), nullable=False)
    coverage_details = db.Column(db.Text, nullable=True)
    exclusions = db.Column(db.Text, nullable=True)
    terms = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<WarrantyPolicy {self.policy_name}>'
