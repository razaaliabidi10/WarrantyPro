import os
import click
from datetime import date, timedelta
from app import create_app, db
from app.models.user import User, Role
from app.models.customer import Customer
from app.models.product import Product, ProductModel, WarrantyPolicy
from app.models.warranty import ProductRegistration, Warranty
from app.models.claim import Claim
from app.models.service import ServiceCenter, Technician

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

@app.cli.command("seed-db")
def seed_db():
    """Seeds the database with initial test data."""
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()

    print("Seeding roles...")
    roles = ['admin', 'warranty_officer', 'technician', 'dealer', 'customer']
    role_objs = {}
    for r in roles:
        role = Role(name=r)
        db.session.add(role)
        role_objs[r] = role
    db.session.commit()

    print("Seeding users...")
    # Admin
    admin_user = User(email='razaali7@gmail.com', role=role_objs['admin'], is_active=True)
    admin_user.set_password('raza@8521')
    db.session.add(admin_user)

    # Warranty Officer
    officer_user = User(email='officer@test.com', role=role_objs['warranty_officer'], is_active=True)
    officer_user.set_password('raza@8521')
    db.session.add(officer_user)

    # Technician
    tech_user = User(email='tech@test.com', role=role_objs['technician'], is_active=True)
    tech_user.set_password('raza@8521')
    db.session.add(tech_user)

    # Customer
    cust_user = User(email='customer@test.com', role=role_objs['customer'], is_active=True)
    cust_user.set_password('raza@8521')
    db.session.add(cust_user)

    db.session.commit()

    # Profiles
    customer = Customer(user_id=cust_user.id, full_name='John Doe', phone='1234567890')
    db.session.add(customer)

    center = ServiceCenter(name='Main Hub', city='New York', address='123 Main St', email='hub@test.com', phone='1112223333', is_active=True)
    db.session.add(center)
    db.session.commit()

    tech = Technician(user_id=tech_user.id, service_center_id=center.id, full_name='Bob Fixer', specialization='Hardware', is_available=True)
    db.session.add(tech)

    # Products & Warranty Policy
    # 1. Samsung
    prod1 = Product(category='Electronics', brand='Samsung', name='Galaxy S', description='Flagship phones')
    db.session.add(prod1)
    # 2. Apple
    prod2 = Product(category='Electronics', brand='Apple', name='iPhone', description='Smartphones')
    db.session.add(prod2)
    # 3. Sony
    prod3 = Product(category='Home Appliances', brand='Sony', name='Bravia TV', description='Smart TVs')
    db.session.add(prod3)
    # 4. Dell
    prod4 = Product(category='Computers', brand='Dell', name='XPS Laptop', description='Premium laptops')
    db.session.add(prod4)
    # 5. LG
    prod5 = Product(category='Home Appliances', brand='LG', name='Smart Refrigerator', description='Smart home appliances')
    db.session.add(prod5)
    # 6. Asus
    prod6 = Product(category='Computers', brand='Asus', name='ROG Zephyrus', description='Gaming laptops')
    db.session.add(prod6)
    # 7. Nikon
    prod7 = Product(category='Cameras', brand='Nikon', name='DSLR Series', description='Professional cameras')
    db.session.add(prod7)
    db.session.commit()

    # Models
    model1 = ProductModel(product_id=prod1.id, model_name='S24 Ultra', model_number='SM-S928', warranty_period_months=12, is_active=True)
    db.session.add(model1)
    
    model2 = ProductModel(product_id=prod2.id, model_name='iPhone 15 Pro', model_number='A2848', warranty_period_months=12, is_active=True)
    db.session.add(model2)
    
    model3 = ProductModel(product_id=prod3.id, model_name='Bravia XR 65"', model_number='XR-65A80L', warranty_period_months=24, is_active=True)
    db.session.add(model3)

    model4 = ProductModel(product_id=prod4.id, model_name='XPS 15 9530', model_number='XPS-9530', warranty_period_months=12, is_active=True)
    db.session.add(model4)

    model5 = ProductModel(product_id=prod5.id, model_name='InstaView Door-in-Door', model_number='LRSOS2706S', warranty_period_months=36, is_active=True)
    db.session.add(model5)

    model6 = ProductModel(product_id=prod6.id, model_name='ROG Zephyrus G14', model_number='GA402XZ', warranty_period_months=24, is_active=True)
    db.session.add(model6)

    model7 = ProductModel(product_id=prod7.id, model_name='Nikon D850', model_number='D850-BODY', warranty_period_months=12, is_active=True)
    db.session.add(model7)
    db.session.commit()
    
    # Policies
    policy1 = WarrantyPolicy(product_model_id=model1.id, policy_name='Samsung Standard 1 Year', coverage_details='Full parts and labor', exclusions='Water damage, physical abuse', is_active=True)
    db.session.add(policy1)
    
    policy2 = WarrantyPolicy(product_model_id=model2.id, policy_name='Apple Limited Warranty', coverage_details='Hardware repairs', exclusions='Accidental damage', is_active=True)
    db.session.add(policy2)
    
    policy3 = WarrantyPolicy(product_model_id=model3.id, policy_name='Sony 2 Year Warranty', coverage_details='Panel and electronics', exclusions='Screen burn-in', is_active=True)
    db.session.add(policy3)

    policy4 = WarrantyPolicy(product_model_id=model4.id, policy_name='Dell Base Warranty', coverage_details='Hardware and mail-in service', exclusions='Software issues', is_active=True)
    db.session.add(policy4)

    policy5 = WarrantyPolicy(product_model_id=model5.id, policy_name='LG Compressor Warranty', coverage_details='10 Year Linear Compressor, 1 Year Parts/Labor', exclusions='Cosmetic damage', is_active=True)
    db.session.add(policy5)

    policy6 = WarrantyPolicy(product_model_id=model6.id, policy_name='Asus Premium Care', coverage_details='Global warranty and ADP', exclusions='Unauthorized modifications', is_active=True)
    db.session.add(policy6)

    policy7 = WarrantyPolicy(product_model_id=model7.id, policy_name='Nikon 1 Year Limited', coverage_details='Manufacturing defects', exclusions='Lens scratches, drops', is_active=True)
    db.session.add(policy7)
    db.session.commit()

    # Registration & Warranty
    reg = ProductRegistration(customer_id=customer.id, product_model_id=model1.id, serial_number='SN-123456', purchase_date=date.today() - timedelta(days=30), retailer_name='Best Buy')
    db.session.add(reg)
    db.session.commit()

    warranty = Warranty(registration_id=reg.id, policy_id=policy1.id, start_date=reg.purchase_date, end_date=reg.purchase_date + timedelta(days=365), status='active')
    db.session.add(warranty)
    db.session.commit()

    # Claim
    claim = Claim(customer_id=customer.id, warranty_id=warranty.id, claim_type='hardware_defect', description='Screen flickering randomly.', status='under_review')
    db.session.add(claim)
    db.session.commit()

    print("Seeding complete! You can now log in with:")
    print("Admin: razaali7@gmail.com / raza@8521")
    print("Customer: customer@test.com / raza@8521")
    print("Technician: tech@test.com / raza@8521")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
