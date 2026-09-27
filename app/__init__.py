from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    # ── Inject `now` as a Jinja2 global so every template can use now() ──
    from datetime import datetime, timezone
    app.jinja_env.globals['now'] = lambda: datetime.now(timezone.utc)

    # Register blueprints
    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from app.warranty import warranty as warranty_blueprint
    app.register_blueprint(warranty_blueprint, url_prefix='/warranty')

    from app.claims import claims as claims_blueprint
    app.register_blueprint(claims_blueprint, url_prefix='/claims')

    from app.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from app.api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    from app.officer import officer as officer_blueprint
    app.register_blueprint(officer_blueprint, url_prefix='/officer')

    # Register error handlers
    from app.main.routes import register_error_handlers
    register_error_handlers(app)

    # Ensure upload folder exists and serve uploads
    import os
    from flask import send_from_directory
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    return app


@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))
