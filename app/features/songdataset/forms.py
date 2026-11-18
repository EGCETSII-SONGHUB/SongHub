from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import URL, DataRequired, Length, Optional

from app.features.dataset.models import PublicationType


def _publication_type_choices():
    return [(pt.value, pt.name.replace("_", " ").title()) for pt in PublicationType]


class SongAuthorForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    affiliation = StringField("Affiliation", validators=[Optional(), Length(max=120)])
    orcid = StringField("ORCID", validators=[Optional(), Length(max=120)])

    class Meta:
        csrf = False


class SongDatasetForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=120)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=3)])
    publication_type = SelectField(
        "Publication type",
        choices=_publication_type_choices(),
        default=PublicationType.NONE.value,
        validators=[Optional()],
    )
    publication_doi = StringField("Publication DOI", validators=[Optional(), URL()])
    dataset_doi = StringField("Dataset DOI", validators=[Optional(), URL()])
    tags = StringField("Tags (separated by commas)", validators=[Optional(), Length(max=120)])
    filename = StringField("CSV Filename", validators=[Optional()])
    authors = FieldList(FormField(SongAuthorForm))
    submit = SubmitField("Upload song dataset")


class SongDatasetEditForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=120)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=3)])
    publication_type = SelectField(
        "Publication type",
        choices=_publication_type_choices(),
        default=PublicationType.NONE.value,
        validators=[Optional()],
    )
    publication_doi = StringField("Publication DOI", validators=[Optional(), URL()])
    tags = StringField("Tags (separated by commas)", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Save changes")
