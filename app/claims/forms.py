from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional


class ClaimStatusUpdateForm(FlaskForm):
    new_status = SelectField('New Status', choices=[
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('assigned', 'Assigned'),
        ('in_repair', 'In Repair'),
        ('ready', 'Ready for Pickup'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes / Reason', validators=[Optional()])
    submit = SubmitField('Update Status')
