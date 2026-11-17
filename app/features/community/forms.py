from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional

ALLOWED_LOGO_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "svg", "webp"]


class CommunityForm(FlaskForm):
    """Form for creating and editing a community."""

    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=120)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=5000)])
    logo = FileField(
        "Logo",
        validators=[
            Optional(),
            FileAllowed(
                ALLOWED_LOGO_EXTENSIONS,
                "Logo must be an image file (png, jpg, jpeg, gif, svg, webp).",
            ),
        ],
    )
    submit = SubmitField("Save community")


class AddDatasetToCommunityForm(FlaskForm):
    """Form for adding a user-owned dataset to a community."""

    dataset_id = IntegerField("Dataset", validators=[DataRequired()])
    submit = SubmitField("Add dataset")


class AddCuratorForm(FlaskForm):
    """Form for adding a registered user as curator of a community by email."""

    email = StringField("Curator email", validators=[DataRequired(), Email(), Length(max=256)])
    submit = SubmitField("Add curator")
