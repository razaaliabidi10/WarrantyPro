from app.models.user import User, Role
from app.models.customer import Customer
from app.models.product import Product, ProductModel
from app import db
import datetime

def test_customer_dashboard_access_denied_if_not_logged_in(client):
    response = client.get('/warranty/dashboard', follow_redirects=True)
    # Should redirect to login
    assert b'Welcome Back' in response.data

def test_admin_dashboard_access_denied_for_customer(client, app):
    with app.app_context():
        customer_role = Role.query.filter_by(name='customer').first()
        user = User(email='cust@test.com', role=customer_role)
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()
        
        customer = Customer(user_id=user.id, full_name='Cust')
        db.session.add(customer)
        db.session.commit()

    # Login
    client.post('/auth/login', data={'email': 'cust@test.com', 'password': 'pass123'})
    
    # Try admin route
    response = client.get('/admin/dashboard', follow_redirects=True)
    # Should be 403 or redirect
    assert response.status_code in [403, 200]
    if response.status_code == 200:
        assert b'You do not have permission' in response.data or b'Forbidden' in response.data or b'Access Denied' in response.data
