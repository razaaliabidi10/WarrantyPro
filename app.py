import os
import jinja2
from dotenv import load_dotenv
from datetime import datetime, timezone
from flask import render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_login import login_user, logout_user, current_user, login_required
from supabase import create_client, Client
from app import create_app, db, csrf
from app.models.user import User, Role
from app.models.customer import Customer
from app.utils.audit import log_action
from app.utils.helpers import allowed_file, save_uploaded_file

try:
    from supabase_auth.errors import AuthApiError, AuthError
except ImportError:
    class AuthApiError(Exception):
        pass
    class AuthError(Exception):
        pass

load_dotenv()

# Initialize the complete WarrantyPro Flask application with all blueprints
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
app.secret_key = os.getenv("SECRET_KEY", "session_secret_key_antigravity_dev_12345")

# Enable both root templates/ (login.html, callback.html) and app/templates/
basedir = os.path.abspath(os.path.dirname(__file__))
root_templates = os.path.join(basedir, 'templates')
if os.path.exists(root_templates):
    app.jinja_loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader(root_templates),
        app.jinja_loader
    ])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_role_dashboard_url(user):
    """Returns the actual dashboard endpoint URL for the user's role."""
    if not user:
        return url_for('login')
    if user.is_admin():
        return url_for('admin.dashboard')
    elif user.is_warranty_officer():
        return url_for('officer.dashboard')
    elif user.is_technician():
        return url_for('admin.technician_dashboard')
    else:
        return url_for('warranty.dashboard')


def redirect_to_role_dashboard(user):
    """Redirects to the proper role dashboard view."""
    return redirect(get_role_dashboard_url(user))


def get_or_create_local_user(email, full_name=None):
    """
    Bridges Supabase user to local database.
    Case A: Email exists locally -> returns existing User.
    Case B: Email does NOT exist locally (e.g. a new Google login) ->
            auto-creates User with role 'customer' and Customer profile.
    """
    clean_email = email.lower().strip()
    local_user = User.query.filter_by(email=clean_email).first()

    if not local_user:
        # Case B: New user, set default role to 'customer'
        customer_role = Role.query.filter_by(name='customer').first()
        if not customer_role:
            customer_role = Role(name='customer')
            db.session.add(customer_role)
            db.session.flush()

        display_name = full_name or clean_email.split('@')[0].capitalize()
        local_user = User(
            email=clean_email,
            role_id=customer_role.id,
            is_active=True,
            full_name=display_name
        )
        # Random password since authentication happens via Supabase / OAuth
        local_user.set_password(os.urandom(16).hex())
        db.session.add(local_user)
        db.session.flush()

        # Create linked Customer profile
        profile = Customer(
            user_id=local_user.id,
            full_name=display_name
        )
        db.session.add(profile)
        db.session.commit()

        log_action('user_registered', target_table='users', target_id=local_user.id,
                   details=f'New customer auto-created via Supabase Auth: {local_user.email}')
    return local_user


def populate_session_and_login(local_user, access_token=None):
    """
    Restores all legacy session variables and logs the user in via Flask-Login.
    """
    login_user(local_user, remember=True)
    local_user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    role_name = local_user.role.name if (local_user.role and hasattr(local_user.role, 'name')) else 'customer'
    session['user_id'] = local_user.id
    session['email'] = local_user.email
    session['role'] = role_name
    session['user'] = {
        'id': str(local_user.id),
        'email': local_user.email,
        'role': role_name,
        'access_token': access_token
    }

    log_action('user_login', target_table='users', target_id=local_user.id,
               details=f'User logged in: {local_user.email}')


@app.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect_to_role_dashboard(current_user)
    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/signup', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect_to_role_dashboard(current_user)
        return render_template('signup.html')

    # POST: Process new user registration
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    photo = request.files.get('profile_photo')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    if not name:
        msg = 'Full name is required.'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))

    if not email or '@' not in email or '.' not in email:
        msg = 'A valid email address is required.'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))

    # Password strength check: min 8 chars, uppercase, lowercase, special character
    if len(password) < 8:
        msg = 'Password must be at least 8 characters long.'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))
    if not any(c.isupper() for c in password):
        msg = 'Password must contain at least one uppercase letter (A-Z).'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))
    if not any(c.islower() for c in password):
        msg = 'Password must contain at least one lowercase letter (a-z).'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?~`\'"' for c in password):
        msg = 'Password must contain at least one special character (!@#$%^&*...).'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))

    # Check if user already exists locally
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        msg = 'An account with this email address already exists. Please log in.'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('signup'))

    # Handle optional profile picture upload
    profile_photo_path = None
    if photo and photo.filename:
        if allowed_file(photo.filename):
            try:
                profile_photo_path = save_uploaded_file(photo, subfolder='profiles')
            except Exception:
                profile_photo_path = None
        else:
            msg = 'Invalid image format. Supported formats: PNG, JPG, JPEG, WEBP.'
            if is_ajax:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('signup'))

    try:
        # Create User in local database with role 'customer'
        customer_role = Role.query.filter_by(name='customer').first()
        if not customer_role:
            customer_role = Role(name='customer')
            db.session.add(customer_role)
            db.session.flush()

        new_user = User(
            email=email,
            role_id=customer_role.id,
            is_active=True,
            full_name=name,
            profile_photo=profile_photo_path
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        # Create linked Customer profile with optional phone number
        customer_profile = Customer(
            user_id=new_user.id,
            full_name=name,
            phone=phone if phone else None
        )
        db.session.add(customer_profile)
        db.session.commit()

        log_action('user_registered', target_table='users', target_id=new_user.id,
                   details=f'New customer registered: {new_user.email}')

        # Sync to Supabase Auth
        try:
            supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": name,
                        "phone": phone
                    }
                }
            })
        except Exception:
            pass  # Even if Supabase rate-limits email, local database registration succeeded!

        success_msg = 'Your account was created successfully. Please go to the login page.'
        if is_ajax:
            return jsonify({'status': 'success', 'message': success_msg})
        else:
            flash(success_msg, 'success')
            return redirect(url_for('login'))

    except Exception as e:
        db.session.rollback()
        msg = f'Registration error: {str(e)}'
        if is_ajax:
            return jsonify({'status': 'error', 'message': msg}), 500
        flash(msg, 'error')
        return redirect(url_for('signup'))


@app.route('/login', methods=['POST'])
def login_post():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash('Please provide both email and password.', 'error')
        return redirect(url_for('login'))

    # Step 1: Attempt Supabase authentication
    supabase_success = False
    supabase_err_msg = None
    access_token = None
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res and res.user:
            supabase_success = True
            access_token = res.session.access_token if res.session else None
    except (AuthApiError, AuthError) as e:
        supabase_err_msg = getattr(e, 'message', str(e))
    except Exception as e:
        supabase_err_msg = getattr(e, 'message', str(e))

    if supabase_success:
        local_user = get_or_create_local_user(email)
        if not local_user.is_active:
            logout_user()
            session.clear()
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return redirect(url_for('login'))
        populate_session_and_login(local_user, access_token)
        return redirect_to_role_dashboard(local_user)

    # Step 2: Fallback for Legacy Test Accounts (officer@test.com, razaali7@gmail.com, tech@test.com, customer@test.com)
    clean_email = email.lower().strip()
    local_user = User.query.filter_by(email=clean_email).first()
    if local_user and local_user.check_password(password):
        if not local_user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return redirect(url_for('login'))

        # Auto-sync legacy user into Supabase in background
        try:
            supabase.auth.sign_up({"email": clean_email, "password": password})
        except Exception:
            pass

        populate_session_and_login(local_user)
        return redirect_to_role_dashboard(local_user)

    # If neither Supabase nor local credentials matched
    flash(supabase_err_msg or 'Invalid email or password. Please try again.', 'error')
    return redirect(url_for('login'))


@app.route('/auth/google', methods=['GET'])
def auth_google():
    try:
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "http://127.0.0.1:5003/auth/callback"
            }
        })
        return redirect(res.url)
    except Exception as e:
        flash(f'Google OAuth error: {str(e)}', 'error')
        return redirect(url_for('login'))


@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    code = request.args.get('code')
    if code:
        try:
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            if res and res.user:
                user_email = res.user.email
                meta = getattr(res.user, 'user_metadata', {}) or {}
                full_name = meta.get('full_name') or meta.get('name')
                access_token = res.session.access_token if res.session else None

                local_user = get_or_create_local_user(user_email, full_name=full_name)
                populate_session_and_login(local_user, access_token)
                return redirect_to_role_dashboard(local_user)
            else:
                flash('Authentication failed: user not found.', 'error')
                return redirect(url_for('login'))
        except Exception as e:
            flash(f'Failed to exchange authorization code: {str(e)}', 'error')
            return redirect(url_for('login'))

    # If no code in query params, render fallback callback.html to parse #access_token=...
    return render_template('callback.html')


@app.route('/api/set-session', methods=['POST'])
@csrf.exempt
def set_session():
    data = request.get_json(silent=True) or {}
    access_token = data.get('access_token')

    if not access_token:
        return jsonify({"status": "error", "message": "Missing access_token"}), 400

    try:
        user_resp = supabase.auth.get_user(access_token)
        if user_resp and user_resp.user:
            user_email = user_resp.user.email
            meta = getattr(user_resp.user, 'user_metadata', {}) or {}
            full_name = meta.get('full_name') or meta.get('name')

            local_user = get_or_create_local_user(user_email, full_name=full_name)
            populate_session_and_login(local_user, access_token)
            redirect_url = get_role_dashboard_url(local_user)
            return jsonify({"status": "ok", "redirect_url": redirect_url})
        else:
            return jsonify({"status": "error", "message": "Invalid token or user not found"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Bypasses placeholder dashboard and redirects immediately to the user's role panel."""
    if current_user.is_authenticated:
        return redirect_to_role_dashboard(current_user)
    elif session.get('user_id'):
        local_user = User.query.get(session['user_id'])
        if local_user:
            return redirect_to_role_dashboard(local_user)
    return redirect(url_for('login'))


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if current_user.is_authenticated:
        try:
            log_action('user_logout', target_table='users', target_id=current_user.id,
                       details=f'User logged out: {current_user.email}')
        except Exception:
            pass
    session.clear()
    logout_user()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    flash('You have been logged out successfully.', 'info')
    response = make_response(redirect(url_for('login')))
    response.set_cookie('remember_token', '', expires=0, max_age=0)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
