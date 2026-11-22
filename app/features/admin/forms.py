from flask_wtf import FlaskForm
from wtforms import SelectField
from wtforms.validators import DataRequired

from app.features.auth.models import Role


class RoleForm(FlaskForm):
    role = SelectField("Role", choices=[(r, r) for r in Role.ALL], validators=[DataRequired()])