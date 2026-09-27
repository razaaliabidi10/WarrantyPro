from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, make_response, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.auth import auth
from app.auth.forms import RegistrationForm, LoginForm
from app.models.user import User, Role
from app.models.customer import Customer, Dealer
from app.utils.audit import log_action


@auth.route('/register', methods=['GET', 'POST'])
def register():
    return redirect(url_for('signup'))

    form = RegistrationForm()
    if form.validate_on_submit():
        role = Role.query.filter_by(name=form.role.data).first()
        if not role:
            flash('Invalid role selected.', 'danger')
            return render_template('auth/register.html', form=form, title='Register')

        user = User(
            email=form.email.data.lower().strip(),
            role_id=role.id,
            is_active=True
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # get user.id

        if form.role.data == 'customer':
            profile = Customer(
                user_id=user.id,
                full_name=form.full_name.data.strip(),
                phone=form.phone.data.strip() if form.phone.data else None
            )
            db.session.add(profile)
        elif form.role.data == 'dealer':
            profile = Dealer(
                user_id=user.id,
                business_name=form.full_name.data.strip(),
                contact_person=form.full_name.data.strip(),
                phone=form.phone.data.strip() if form.phone.data else None
            )
            db.session.add(profile)

        db.session.commit()
        log_action('user_registered', target_table='users', target_id=user.id,
                   details=f'New {form.role.data} registered: {user.email}')
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form, title='Register')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    return redirect(url_for('login'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            log_action('user_login', target_table='users', target_id=user.id,
                       details=f'User logged in: {user.email}')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)

            if user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif user.is_warranty_officer():
                return redirect(url_for('officer.dashboard'))
            elif user.is_technician():
                return redirect(url_for('admin.technician_dashboard'))
            else:
                return redirect(url_for('warranty.dashboard'))
        elif user and not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'danger')
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    resp = make_response(render_template('auth/login.html', form=form, title='Sign In'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@auth.route('/logout', methods=['GET', 'POST'])
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
        from app.auth.routes import supabase
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
