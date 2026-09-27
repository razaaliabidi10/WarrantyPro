from app.models.user import User, Role
from app import db

def test_login_page(client):
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Welcome Back' in response.data

def test_register_user(client, app):
    response = client.post('/auth/register', data={
        'role': 'customer',
        'full_name': 'Test User',
        'email': 'test@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        assert user is not None
        assert user.role.name == 'customer'
