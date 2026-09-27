from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, BooleanField, SelectField,
                     SubmitField, TextAreaField)
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models.user import User


class RegistrationForm(FlaskForm):
    email = StringField('Email Address', validators=[
        DataRequired(), Email(), Length(max=150)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, message='Password must be at least 8 characters.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=150)])
    phone = StringField('Phone Number', validators=[Length(max=30)])
    role = SelectField('Register As', choices=[
        ('customer', 'Customer'),
        ('dealer', 'Dealer / Retailer')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Account')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data.lower().strip()).first()
        if user:
            raise ValidationError('This email address is already registered. Please log in.')


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')
