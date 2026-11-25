
# Functions in this forms.py dictate how user input is handled
# ============================================================

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Publisher, Article, Newsletter
from django.db import transaction
from django.db.models import Q


# Reader registration
# -------------------
class ReaderRegistrationForm(UserCreationForm):
    """Provide a registration form for reader accounts.

    Extends Django's ``UserCreationForm`` to handle the registration
    of users with the reader role.

    The form collects the username, email address and password
    confirmation fields required to create a reader account.

    The user's role is automatically assigned as ``READER``
    when the account is saved.

    """

    class Meta:
        """Define the model and fields used by the registration form."""

        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def save(self, commit=True):
        """Create and save a reader account.

        Uses the parent ``UserCreationForm`` save method to create
        the user instance without immediately saving it.

        Assigns the reader role before optionally saving the account
        to the database.

        The ``commit`` argument determines whether the user is saved
        immediately or returned as an unsaved instance.

        :param commit: Determines whether the user instance is saved
            to the database.
        :type commit: bool
        :returns: The newly created reader user instance.
        :rtype: CustomUser
        """

        user = super().save(commit=False)
        user.role = CustomUser.Role.READER

        if commit:
            user.save()

        return user


# Journalist registration
# -----------------------
class JournalistRegistrationForm(UserCreationForm):
    """Provide a registration form for journalist accounts.

    Extends Django's ``UserCreationForm`` to support journalist
    registration.

    The form collects the username, email address and password
    confirmation fields required to create a journalist account.

    Journalists can optionally associate their accounts with
    multiple publishers during registration. Independent journalists
    can leave the publisher selection blank.

    Publisher affiliations are stored using the user model's
    many-to-many relationship.

    """

    journalist_publisher = forms.ModelMultipleChoiceField(
        queryset=Publisher.objects.all(),
        required=False,
        label="Select your publishers",
        widget=forms.CheckboxSelectMultiple(),
        help_text=(
            "You can select multiple publishers or leave this blank "
            "if you are an independent journalist."
        )
    )

    class Meta:
        """Define the model and fields used by the registration form."""

        model = CustomUser
        fields = [
            'username',
            'email',
            'password1',
            'password2',
        ]

    @transaction.atomic
    def save(self, commit=True):
        """Create and save a journalist account.

        Uses the parent ``UserCreationForm`` save method to create
        the user instance without immediately saving it.

        Assigns the journalist role before saving the account.

        When ``commit`` is enabled, the user is saved to the database
        and their selected publisher affiliations are assigned.

        The transaction ensures that the user creation and publisher
        association operations are performed atomically.

        :param commit: Determines whether the user instance is saved
            to the database.
        :type commit: bool
        :returns: The newly created journalist user instance.
        :rtype: CustomUser
        """

        user = super().save(commit=False)
        user.role = CustomUser.Role.JOURNALIST

        if commit:
            user.save()
            user.publishers.set(
                self.cleaned_data['journalist_publisher']
            )

        return user


# Editor registration
# -------------------
class EditorRegistrationForm(UserCreationForm):
    """Provide a registration form for editor accounts.

    Extends Django's ``UserCreationForm`` to support editor
    registration.

    The form collects the username, email address and password
    confirmation fields required to create an editor account.

    Editors can associate their accounts with existing publishers
    or register a new publisher during account creation.

    Multiple existing publishers can be selected. Alternatively,
    a new publisher can be created by providing its name and
    an optional description.

    The form prevents editors from selecting existing publishers
    and creating a new publisher simultaneously.

    Publisher names are checked to prevent duplicate registrations.

    """

    editor_publishers = forms.ModelMultipleChoiceField(
        queryset=Publisher.objects.all(),
        required=False,
        label="Select your publishers",
        widget=forms.CheckboxSelectMultiple(),
        help_text=(
            "Select multiple publishers or create a new publisher."
        )
    )

    publisher_name = forms.CharField(
        max_length=255,
        required=False,
        label="Or enter a new publisher name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter publisher name'
        })
    )

    publisher_description = forms.CharField(
        required=False,
        label="Publisher description",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describe your publisher'
        })
    )

    class Meta:
        """Define the model and fields used by the registration form."""

        model = CustomUser
        fields = [
            'username',
            'email',
            'password1',
            'password2',
        ]

    def clean(self):
        """Validate publisher selections and new publisher details.

        Ensures that the editor selects either existing publishers
        or provides details for a new publisher.

        The validation prevents the simultaneous selection of
        existing publishers and creation of a new publisher.

        New publisher names are stripped of surrounding whitespace
        and checked against existing publisher records to prevent
        duplicate names.

        :raises ValidationError: If neither an existing publisher
            nor a new publisher name is provided, or if both are
            supplied simultaneously.
        :returns: The validated form data.
        :rtype: dict
        """

        cleaned_data = super().clean()

        existing = cleaned_data.get('editor_publishers')
        new_name = cleaned_data.get('publisher_name')

        if existing and new_name:
            raise forms.ValidationError(
                "Select an existing publisher OR enter a new one, not both."
            )

        if not existing and not new_name:
            raise forms.ValidationError(
                "Please select a publisher or enter a new publisher."
            )

        if new_name:
            new_name = new_name.strip()

            if not new_name:
                self.add_error(
                    'publisher_name',
                    "Publisher name cannot be blank."
                )

            elif Publisher.objects.filter(
                name__iexact=new_name
            ).exists():
                self.add_error(
                    'publisher_name',
                    "This publisher already exists. Please select it instead."
                )

        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        """Create and save an editor account and publisher associations.

        Uses the parent ``UserCreationForm`` save method to create
        the user instance without immediately saving it.

        Assigns the editor role to the user.

        If ``commit`` is disabled, returns the unsaved user instance.

        Otherwise, the method either associates the editor with
        the selected existing publishers or creates a new publisher
        using the supplied name and description.

        The editor account is then saved and associated with the
        relevant publishers through the many-to-many relationship.

        The transaction ensures that the database operations are
        performed atomically.

        :param commit: Determines whether the user instance and
            publisher associations are saved to the database.
        :type commit: bool
        :returns: The newly created editor user instance.
        :rtype: CustomUser
        """

        user = super().save(commit=False)
        user.role = CustomUser.Role.EDITOR

        if not commit:
            return user

        publishers = self.cleaned_data['editor_publishers']

        if not publishers:
            publisher = Publisher.objects.create(
                name=self.cleaned_data['publisher_name'].strip(),
                description=self.cleaned_data['publisher_description']
            )
            publishers = [publisher]

        user.save()
        user.editor_publishers.set(publishers)

        return user


# Login form
# -----------
class CustomLoginForm(AuthenticationForm):
    """Provide a customised login form for all user roles.

    Extends Django's ``AuthenticationForm`` to support authentication
    for readers, journalists and editors.

    Customises the username and password input widgets by applying
    Bootstrap styling and descriptive placeholder text.

    All user roles access the application through the same login form.
    """

    def __init__(self, *args, **kwargs):
        """Initialise the login form and customise input widgets.

        Calls the parent authentication form initialisation method
        before applying CSS classes and placeholder text to the
        username and password fields.

        :param args: Additional positional arguments passed to
            the parent authentication form.
        :param kwargs: Additional keyword arguments passed to
            the parent authentication form.
        :returns: None.
        :rtype: None
        """

        super().__init__(*args, **kwargs)

        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter your username'
        })

        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })


# Article form
# ------------
class ArticleForm(forms.ModelForm):
    """Provide a form for creating and editing news articles.

    Extends Django's ``ModelForm`` to handle article creation
    and editing by journalists and editors.

    The form allows users to enter an article title and content,
    upload an optional image and select an associated publisher.

    Publisher selection is controlled according to the user's role.

    Journalists can only select publishers with which they are
    affiliated. Publisher selection is optional for journalists,
    allowing independent publication.

    Editors can only select publishers assigned to their accounts.
    Publisher selection is mandatory for editors.

    """

    class Meta:
        """Define the article model and form presentation settings."""

        model = Article

        fields = [
            'title',
            'content',
            'image',
            'publisher',
        ]

        labels = {
            'title': 'Article Title',
            'content': 'Article Content',
            'image': 'Upload an Image',
            'publisher': 'Publisher',
        }

        help_texts = {
            'publisher': (
                'Select a publisher you are affiliated with. '
                'Leave blank if you are an independent journalist.'
            ),
            'image': 'Optional: Upload an image to accompany your article.',
        }

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter article title',
            }),

            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Write your article here...',
            }),

            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),

            'publisher': forms.Select(attrs={
                'class': 'form-select',
            }),
        }

    def __init__(self, *args, **kwargs):
        """Initialise the article form and configure publisher choices.

        Extracts the optional user argument before calling the parent
        ``ModelForm`` initialisation method.

        Publisher choices are restricted according to the user's role.

        For journalists, the available publishers are limited to
        those associated with their accounts. Publisher selection
        is optional, allowing independent articles.

        For editors, the available publishers are limited to those
        assigned to their accounts. Publisher selection is mandatory.

        :param args: Additional positional arguments passed to
            the parent model form.
        :param kwargs: Additional keyword arguments, including
            the optional user instance.
        :returns: None.
        :rtype: None
        """

        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.role == CustomUser.Role.JOURNALIST:

            self.fields['publisher'].queryset = (
                user.publishers.all()
            )
            self.fields['publisher'].required = False
            self.fields['publisher'].empty_label = (
                "Publish independently (no publisher)"
            )
        elif user and user.role == CustomUser.Role.EDITOR:

            self.fields['publisher'].queryset = (
                user.editor_publishers.all()
            )
            self.fields['publisher'].required = True


# Newsletter form
# ---------------
class NewsletterForm(forms.ModelForm):
    """Provide a form for creating and editing newsletters.

    Extends Django's ``ModelForm`` to support newsletter creation
    and editing by journalists and editors.

    Users can provide a newsletter title and description, select
    an associated publisher and include multiple articles.

    Available publishers and articles are filtered according
    to the authenticated user's role.

    Journalists can select publishers with which they are affiliated
    and include approved articles written by themselves or
    associated with their affiliated publishers.

    Independent journalists can create newsletters using their
    own approved articles without selecting a publisher.

    Editors can only select publishers assigned to their accounts
    and include approved articles belonging to those publishers.

    The form also validates that all selected articles belong
    to the selected publisher when a publisher is specified.

    """

    publisher = forms.ModelChoiceField(
        queryset=Publisher.objects.none(),
        required=False,
        label="Select publisher",
        empty_label="Choose a publisher (optional)",
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    class Meta:
        """Define the newsletter model and form presentation settings."""

        model = Newsletter

        fields = [
            'title',
            'description',
            'publisher',
            'articles',
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter newsletter title'
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your newsletter'
            }),

            'articles': forms.CheckboxSelectMultiple(
                    attrs={
                        'class': 'form-check-input',
                    }
            ),
        }

    def __init__(self, *args, **kwargs):
        """Initialise the newsletter form and configure available choices.

        Extracts the optional user argument before calling the parent
        ``ModelForm`` initialisation method.

        The available publishers and articles are filtered according
        to the user's assigned role.

        For journalists, the publisher queryset is restricted to
        their affiliated publishers. Publisher selection remains
        optional.

        Journalists can select approved articles that they authored
        or articles associated with their affiliated publishers.

        For editors, the publisher queryset is restricted to
        their assigned publishers. Publisher selection is mandatory.

        Editors can only select approved articles belonging to
        their assigned publishers.

        :param args: Additional positional arguments passed to
            the parent model form.
        :param kwargs: Additional keyword arguments, including
            the optional user instance.
        :returns: None.
        :rtype: None
        """

        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.role == CustomUser.Role.JOURNALIST:

            self.fields['publisher'].queryset = (
                user.publishers.all()
            )
            self.fields['publisher'].required = False

            self.fields['articles'].queryset = (
                Article.objects.filter(
                    Q(author=user) |
                    Q(publisher__in=user.publishers.all()),
                    approved=True
                ).distinct().order_by('-created_at')
            )
        elif user and user.role == CustomUser.Role.EDITOR:

            self.fields['publisher'].queryset = (
                user.editor_publishers.all()
            )

            self.fields['publisher'].required = True

            self.fields['articles'].queryset = (
                Article.objects.filter(
                    publisher__in=user.editor_publishers.all(),
                    approved=True
                ).order_by('-created_at')
            )

    def clean(self):
        """Validate the relationship between the publisher and articles.

        Retrieves the selected publisher and articles from the
        cleaned form data.

        If a publisher has been selected, verifies that every
        selected article belongs to that publisher.

        An error is added to the articles field if any selected
        article belongs to a different publisher.

        :returns: The validated form data.
        :rtype: dict
        """

        cleaned_data = super().clean()

        publisher = cleaned_data.get('publisher')
        articles = cleaned_data.get('articles')

        if publisher and articles:
            if articles.exclude(publisher=publisher).exists():
                self.add_error(
                    'articles',
                    'Selected articles must belong to the selected publisher.'
                )

        return cleaned_data
