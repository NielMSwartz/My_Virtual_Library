"""WTForms definitions with server-side validation and CSRF protection."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms.fields.choices import SelectChoice
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    URL,
    ValidationError,
)

from app.models import BookStatus, PurchaseStatus, User
from app.services.book_catalog import find_duplicate

STAR_CHOICES = [(0, "No rating")] + [(value, f"{value} star{'s' if value > 1 else ''}") for value in range(1, 6)]


def select_choices(pairs) -> list[SelectChoice]:
    """Convert (value, label) pairs to WTForms' SelectChoice objects."""
    return [SelectChoice(str(value), label) for value, label in pairs]


class BookForm(FlaskForm):
    """Create or edit a book. Set ``book_id`` before validating an edit."""

    book_id: int | None = None

    title = StringField("Title", validators=[DataRequired(), Length(max=300)])
    authors = StringField("Author(s)", default="Unknown author", validators=[Length(max=300)])
    cover_url = StringField("Cover image URL", validators=[Optional(), URL(), Length(max=1000)])
    cover_small_url = HiddenField(validators=[Optional(), URL(), Length(max=1000)])
    isbn = StringField("ISBN", validators=[Optional(), Length(max=32)])
    publisher = StringField("Publisher", validators=[Optional(), Length(max=200)])
    publication_year = IntegerField(
        "Publication year", validators=[Optional(), NumberRange(min=1000, max=2100)]
    )
    page_count = IntegerField("Total pages", validators=[Optional(), NumberRange(min=0, max=50000)])
    current_page = IntegerField(
        "Current page", default=0, validators=[Optional(), NumberRange(min=0, max=50000)]
    )
    status = SelectField(
        "Reading status", choices=select_choices(BookStatus.CHOICES), default=BookStatus.WANT_TO_READ
    )
    genre = StringField("Genre / category", validators=[Optional(), Length(max=120)])
    rating = SelectField("Personal rating", choices=select_choices(STAR_CHOICES), coerce=int, default=0)
    description = TextAreaField("Description", validators=[Optional()])
    notes = TextAreaField("Personal notes", validators=[Optional()])
    review = TextAreaField("Review", validators=[Optional()])

    purchase_status = SelectField(
        "Purchase status", choices=select_choices(PurchaseStatus.CHOICES), default=PurchaseStatus.OWNED
    )
    price = DecimalField("Price", validators=[Optional(), NumberRange(min=0)])
    currency = StringField("Currency", default="USD", validators=[Optional(), Length(min=3, max=3)])
    purchase_link = StringField("Purchase link", validators=[Optional(), URL(), Length(max=1000)])

    date_started = DateField("Date started", format="%Y-%m-%d", validators=[Optional()])
    date_finished = DateField("Date finished", format="%Y-%m-%d", validators=[Optional()])

    source = HiddenField(default="manual")
    external_id = HiddenField()

    submit = SubmitField("Save book")

    def validate_current_page(self, field) -> None:
        if field.data is None:
            return
        if self.page_count.data is not None and field.data > self.page_count.data:
            raise ValidationError("Current page cannot be greater than the total page count.")

    def validate_date_finished(self, field) -> None:
        if field.data and self.date_started.data and field.data < self.date_started.data:
            raise ValidationError("Finish date cannot be earlier than the start date.")

    def validate_title(self, field) -> None:
        duplicate = find_duplicate(
            field.data,
            self.authors.data,
            self.isbn.data,
            exclude_id=self.book_id,
        )
        if duplicate is not None:
            raise ValidationError(
                f'This looks like "{duplicate.title}" already in your library. Edit that book instead.'
            )


class EmptyForm(FlaskForm):
    """Minimal form used for CSRF-protected POST actions such as delete."""


class StatusForm(FlaskForm):
    status = SelectField("Reading status", choices=select_choices(BookStatus.CHOICES))
    submit = SubmitField("Update status")


class ProgressForm(FlaskForm):
    page = IntegerField("Current page", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Update bookmark")

    def validate_page(self, field) -> None:
        if field.data is None:
            return
        if field.data < 0:
            raise ValidationError("Page cannot be negative.")
        if getattr(self, "page_count", None) is not None and field.data > self.page_count:
            raise ValidationError("Page cannot be greater than the total page count.")


class SettingsForm(FlaskForm):
    yearly_goal = IntegerField(
        "Books to finish this year", validators=[Optional(), NumberRange(min=0, max=10000)]
    )
    submit = SubmitField("Save goal")


class OnlineSearchForm(FlaskForm):
    query = StringField("Title, author or ISBN", validators=[DataRequired(), Length(max=200)])
    submit = SubmitField("Search")


class SetupForm(FlaskForm):
    """Create the one private account, only possible while no user exists."""

    email = StringField(
        "Email address",
        validators=[DataRequired(), Email(), Length(max=254)],
        filters=[lambda value: User.normalize_email(value) if value else value],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")

    def validate_email(self, field) -> None:
        field.data = User.normalize_email(field.data)
        if User.count() > 0:
            raise ValidationError("This bookshelf already has an account. Sign in instead.")
        if User.find_by_email(field.data) is not None:
            raise ValidationError("That email is already in use.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email address",
        validators=[DataRequired(), Email(), Length(max=254)],
        filters=[lambda value: User.normalize_email(value) if value else value],
    )
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")

    def validate_email(self, field) -> None:
        field.data = User.normalize_email(field.data)


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField(
        "New password",
        validators=[DataRequired(), Length(min=8, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit_password = SubmitField("Change password")


class LogoutForm(FlaskForm):
    """CSRF-protected logout button used in Settings."""
