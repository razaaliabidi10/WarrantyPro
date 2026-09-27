from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import (StringField, SelectField, TextAreaField, SubmitField,
                     HiddenField, IntegerField)
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from app.models.warranty import ProductRegistration


class ProductRegistrationForm(FlaskForm):
    product_model_id = SelectField('Product Model', coerce=int, validators=[DataRequired()])
    serial_number = StringField('Serial Number', validators=[DataRequired(), Length(max=100)])
    purchase_date = DateField('Purchase Date', validators=[DataRequired()])
    retailer_name = StringField('Retailer / Store Name', validators=[Optional(), Length(max=200)])
    notes = TextAreaField('Additional Notes', validators=[Optional()])
    invoice_file = FileField('Upload Invoice (PDF/Image)', validators=[
        Optional(),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg'], 'Only PDF and image files are allowed.')
    ])
    submit = SubmitField('Register Product')

    def validate_serial_number(self, field):
        existing = ProductRegistration.query.filter_by(serial_number=field.data.strip()).first()
        if existing:
            raise ValidationError('This serial number is already registered in our system.')


class ClaimSubmissionForm(FlaskForm):
    warranty_id = HiddenField('Warranty ID')
    claim_type = SelectField('Claim Type', choices=[
        ('hardware_defect', 'Hardware Defect'),
        ('physical_damage', 'Physical Damage'),
        ('software_issue', 'Software Issue'),
        ('other', 'Other Issue'),
    ], validators=[DataRequired()])
    description = TextAreaField('Describe the Issue', validators=[
        DataRequired(),
        Length(min=20, message='Please provide at least 20 characters of description.')
    ])
    attachments = MultipleFileField('Upload Evidence (Photos/Documents)', validators=[Optional()])
    submit = SubmitField('Submit Claim')


class FeedbackForm(FlaskForm):
    rating = SelectField('Rating', choices=[
        ('5', '⭐⭐⭐⭐⭐ Excellent'),
        ('4', '⭐⭐⭐⭐ Good'),
        ('3', '⭐⭐⭐ Average'),
        ('2', '⭐⭐ Poor'),
        ('1', '⭐ Very Poor'),
    ], validators=[DataRequired()])
    comments = TextAreaField('Comments', validators=[Optional()])
    submit = SubmitField('Submit Feedback')
