import pytest
from app import create_app, db
from app.models.user import User, Role

@pytest.fixture
def app():
    app = create_app('testing')
    
    # In testing mode, we use an in-memory SQLite DB
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })
    
    with app.app_context():
        db.create_all()
        
        # Seed basic roles
        for r in ['admin', 'warranty_officer', 'technician', 'dealer', 'customer']:
            role = Role(name=r)
            db.session.add(role)
        db.session.commit()
        
        yield app
        
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
