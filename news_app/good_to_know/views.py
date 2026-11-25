
# Views functions are largely developed and adapted from the
# previous eCommerce project.

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
    permission_required)
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

import logging
import requests

from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from django.urls import reverse_lazy

from .models import Article, Newsletter, CustomUser, Publisher
from .forms import (
    ArticleForm,
    NewsletterForm,
    ReaderRegistrationForm,
    JournalistRegistrationForm,
    EditorRegistrationForm,
    CustomLoginForm
)

# Functions for API use
from .serializers import (PublisherSerializer,
                          ArticleSerializer,
                          NewsletterSerializer,
                          UserSerializer,)
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import authentication_classes
# from .functions.jsonplaceholder import get_jsonplaceholder_posts
from rest_framework.exceptions import (
    PermissionDenied as DRFPermissionDenied,
    ValidationError
)
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)

User = get_user_model()


# Role checks
# ===========
#
# The following functions provide role checks for use by other
# view functions and access-control decorators.


def is_reader(user):
    """Check whether the user is an authenticated reader.

    :param user: The user whose role is being checked.
    :type user: CustomUser
    :returns: ``True`` if the user is authenticated and has the reader role;
        otherwise, ``False``.
    :rtype: bool
    """
    return user.is_authenticated and user.role == CustomUser.Role.READER


def is_journalist(user):
    """Check whether the user is an authenticated journalist.

    :param user: The user whose role is being checked.
    :type user: CustomUser
    :returns: ``True`` if the user is authenticated and has the journalist
        role; otherwise, ``False``.
    :rtype: bool
    """
    return user.is_authenticated and user.role == CustomUser.Role.JOURNALIST


def is_editor(user):
    """Check whether the user is an authenticated editor.

    :param user: The user whose role is being checked.
    :type user: CustomUser
    :returns: ``True`` if the user is authenticated and has the editor role;
        otherwise, ``False``.
    :rtype: bool
    """
    return user.is_authenticated and user.role == CustomUser.Role.EDITOR


# Registration
# ============
#
# The following functions register users according to their assigned roles
# and return success messages. These functions are publicly accessible
# and do not require authentication.


# Reader registration
# -------------------
def register_reader(request):
    """Register a new reader account.

    Handles reader registration using the reader registration form.
    On successful submission, the user is created, logged in, and
    redirected to the login page.
    """
    if request.method == 'POST':
        form = ReaderRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(request,
                             'Your reader account has been created.'
                             'Please login')
            return redirect('login')

    else:
        form = ReaderRegistrationForm()

    return render(
        request,
        'good_to_know/register.html',
        {'form': form, 'role': 'Reader'}
    )


# Journalist registration
# -----------------------
def register_journalist(request):
    """Register a new journalist account.

    Handles journalist registration using the journalist registration form.
    On successful submission, the account is created, the user is logged in,
    and the user is redirected to the login page.
    """
    if request.method == 'POST':
        form = JournalistRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(
                request,
                'Your journalist account has been created. Please login'
            )

            return redirect('login')

    else:
        form = JournalistRegistrationForm()

    return render(
        request,
        'good_to_know/register.html',
        {'form': form, 'role': 'Journalist'}
    )


# Editor registration
# -------------------
def register_editor(request):
    """Register a new editor account.

    Handles editor registration using the editor registration form.
    On successful submission, the account is created and the user
    is redirected to the login page.
    """
    if request.method == 'POST':
        form = EditorRegistrationForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Editor account successfully created. Please login'
            )

            return redirect('login')

    else:
        form = EditorRegistrationForm()

    return render(
        request,
        'good_to_know/register.html',
        {'form': form, 'role': 'Editor'}
    )


# Welcome, login, logout and home pages
# =====================================
#
# The welcome page serves as the public-facing landing page for the
# application.
#
# The login functionality uses the custom user model, allowing users
# with different roles to authenticate through the same login page.
#
# Following successful authentication, users are redirected to the
# appropriate home page or dashboard according to their assigned role.


# Welcome page
# ------------
def welcome(request):
    """Display the public welcome page.

    Renders the welcome page template for visitors accessing the
    application.
    """
    return render(request, 'good_to_know/welcome.html')


# Login
# -----
class RoleBasedLoginView(LoginView):
    """Provide role-based user authentication.

    Uses the custom login form to authenticate users across all
    application roles. Following successful authentication, users
    are redirected to the appropriate page according to their role.
    """

    template_name = 'good_to_know/login.html'
    authentication_form = CustomLoginForm

    def get_success_url(self):
        """Determine the post-login redirect URL.

        Returns a different destination depending on the authenticated
        user's assigned role.

        :returns: The URL of the appropriate home page or dashboard.
        :rtype: str
        """

        user = self.request.user

        if user.role == CustomUser.Role.READER:
            return reverse_lazy('home')

        elif user.role == CustomUser.Role.JOURNALIST:
            return reverse_lazy('journalist_dashboard')

        elif user.role == CustomUser.Role.EDITOR:
            return reverse_lazy('editor_dashboard')

        return reverse_lazy('home')


# Logout
# ------
@login_required
def logout_user(request):
    """Log out the authenticated user.

    Ends the current user's authenticated session and redirects them
    to the public welcome page.

    :param request: The HTTP request received from the authenticated user.
    :type request: HttpRequest
    :returns: A redirect response to the welcome page.
    :rtype: HttpResponseRedirect
    """
    logout(request)
    return redirect('welcome')


# Home page
# ---------
def home(request):
    """Display the application home page.

    Retrieves and displays approved articles and newsletters.
    Articles are ordered by creation date, with the most recent
    publications displayed first. Related authors, publishers,
    and newsletter articles are retrieved to support efficient
    template rendering.
    """

    articles = Article.objects.filter(
        approved=True
    ).select_related(
        'author', 'publisher'
    ).order_by('-created_at')

    newsletters = Newsletter.objects.filter(
        approved=True
    ).distinct().prefetch_related(
        'articles'
    ).order_by('-created_at')

    return render(
        request,
        'good_to_know/home.html',
        {
            'articles': articles,
            'newsletters': newsletters,
        }
    )


# Publication details
# ===================
#
# The following views provide the functionality required to display
# individual publication details.
#
# Both views are linked throughout the application. Newsletters are
# structured to contain multiple articles, whereas each article is
# displayed individually.


# Article detail
# --------------
@login_required
def article_detail(request, article_id):
    """Display the details of an individual article.

    Retrieves an article using its ID and displays its details to
    authenticated users.

    Approved articles are accessible to all authenticated users.
    Unapproved articles can only be accessed by their journalist
    author or an editor associated with the article's publisher.
    Users without the required permissions are denied access.

    :param request: The HTTP request received from the authenticated user.
    :type request: HttpRequest
    :param article_id: The unique identifier of the article.
    :type article_id: int
    :raises PermissionDenied: If the user does not have permission to
        access an unapproved article.
    :returns: A rendered response containing the article details.
    :rtype: HttpResponse
    """
    article = get_object_or_404(
        Article.objects.select_related(
            'author', 'publisher'
        ),
        id=article_id
    )
    if not article.approved:

        journalist_owner = (
            request.user.is_authenticated
            and request.user == article.author
        )
        editor_owner = (
            is_editor(request.user)
            and article.publisher_id is not None
            and request.user.editor_publishers.filter(
                pk=article.publisher_id
            ).exists()
        )
        if not (journalist_owner or editor_owner):
            raise PermissionDenied
    return render(
        request,
        'good_to_know/article_detail.html',
        {'article': article}
    )


# Newsletter detail
# -----------------
@login_required
def newsletter_detail(request, newsletter_id):
    """Display the details of an individual newsletter.

    Retrieves a newsletter using its ID and displays its details,
    together with its approved articles.

    Approved newsletters are accessible to all authenticated users.
    Unapproved newsletters can only be accessed by their journalist
    author or an editor associated with the newsletter's publisher.
    Users without the required permissions are denied access.

    :param request: The HTTP request received from the authenticated user.
    :type request: HttpRequest
    :param newsletter_id: The unique identifier of the newsletter.
    :type newsletter_id: int
    :raises PermissionDenied: If the user does not have permission to
        access an unapproved newsletter.
    :returns: A rendered response containing the newsletter details
        and its approved articles.
    :rtype: HttpResponse
    """
    newsletter = get_object_or_404(
        Newsletter.objects.select_related(
            'author'
        ).prefetch_related('articles'),
        id=newsletter_id
    )
    journalist_owner = (
        request.user == newsletter.author
    )
    editor_owner = (
        is_editor(request.user)
        and newsletter.publisher_id is not None
        and request.user.editor_publishers.filter(
            pk=newsletter.publisher_id
        ).exists()
    )
    if not newsletter.approved:
        if not (journalist_owner or editor_owner):
            raise PermissionDenied
    articles = newsletter.articles.filter(
        approved=True
    )
    return render(
        request,
        'good_to_know/newsletter_detail.html',
        {
            'newsletter': newsletter,
            'articles': articles,
        }
    )


# Dashboards
# ==========
#
# The application provides separate dashboards for readers, journalists
# and editors.
#
# The reader dashboard displays the publishers and journalists to which
# the reader has subscribed.
#
# The journalist dashboard displays the journalist's own publications,
# including both approved and pending articles and newsletters.
#
# The editor dashboard displays publications awaiting approval, as well
# as approved publications associated with the editor's publishers.


# Reader dashboard
# ----------------
@login_required
@user_passes_test(is_reader)
def reader_dashboard(request):
    """Display the reader dashboard.

    Retrieves and displays the publishers and journalists to which
    the authenticated reader has subscribed.

    Access is restricted to authenticated users with the reader role.

    :param request: The HTTP request received from the authenticated user.
    :type request: HttpRequest
    :returns: A rendered response containing the reader's subscriptions.
    :rtype: HttpResponse
    """

    publishers = request.user.subscribed_publishers.all()

    journalists = request.user.subscribed_journalists.all()

    return render(
        request,
        'good_to_know/reader_dashboard.html',
        {
            'publishers': publishers,
            'journalists': journalists,
        }
    )


# Journalist dashboard
# --------------------
@login_required
@user_passes_test(is_journalist)
def journalist_dashboard(request):
    """Display the journalist dashboard.

    Retrieves and displays articles and newsletters belonging to
    the authenticated journalist. Publications are ordered by
    creation date, with the most recent displayed first.

    Both approved and pending publications are included.

    Access is restricted to authenticated users with the journalist role.

    :param request: The HTTP request received from the authenticated user.
    :type request: HttpRequest
    :returns: A rendered response containing the journalist's publications.
    :rtype: HttpResponse
    """

    articles = Article.objects.filter(
        author=request.user
    ).order_by('-created_at')

    newsletters = Newsletter.objects.filter(
        author=request.user
    ).prefetch_related(
        'articles'
    ).order_by('-created_at')

    return render(
        request,
        'good_to_know/journalist_dashboard.html',
        {
            'articles': articles,
            'newsletters': newsletters,
        }
    )


# Editor dashboard
# ----------------
@login_required
@user_passes_test(is_editor)
def editor_dashboard(request):
    """Display the editor dashboard.

    Retrieves articles and newsletters associated with the
    authenticated editor's publishers.

    Publications are separated into pending and approved categories
    to allow editors to review submissions and manage existing
    publications.

    The dashboard also displays the publishers associated with
    the authenticated editor.

    Access is restricted to authenticated users with the editor role.

    :param request: The HTTP request received from the authenticated user.
    :type request: HttpRequest
    :returns: A rendered response containing the editor's publications,
        approval categories and associated publishers.
    :rtype: HttpResponse
    """

    articles = list(
        editor_articles(request.user)
        .order_by('-created_at')
    )

    newsletters = list(
        editor_newsletters(request.user)
        .order_by('-created_at')
    )

    pending_articles = [
        article for article in articles
        if not article.approved
    ]

    approved_articles = [
        article for article in articles
        if article.approved
    ]

    pending_newsletters = [
        newsletter for newsletter in newsletters
        if not newsletter.approved
    ]

    approved_newsletters = [
        newsletter for newsletter in newsletters
        if newsletter.approved
    ]

    return render(
        request,
        'good_to_know/editor_dashboard.html',
        {
            'articles': articles,
            'newsletters': newsletters,
            'pending_articles': pending_articles,
            'approved_articles': approved_articles,
            'pending_newsletters': pending_newsletters,
            'approved_newsletters': approved_newsletters,
            'publishers': request.user.editor_publishers.all(),
        }
    )


# Create publisher
# ----------------
@login_required
@user_passes_test(is_editor)
@permission_required(
    'good_to_know.add_publisher',
    raise_exception=True
)
def create_publisher(request):
    """Create a new publisher.

    Allows authenticated editors with the required publisher creation
    permission to create a publisher.

    The submitted publisher name is validated to ensure that it is
    not empty or already in use. Publisher creation is performed
    within an atomic database transaction, and the newly created
    publisher is associated with the editor.

    Success and error messages are displayed according to the
    outcome of the operation. If an exception occurs, the failure
    is recorded in the application log.

    :param request: The HTTP request received from the authenticated editor.
    :type request: HttpRequest
    :returns: A redirect response following successful creation, or a
        rendered response containing the publisher creation form.
    :rtype: HttpResponse
    """

    if request.method == 'POST':

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(
                request,
                'Please enter a publisher name.'
            )

        elif Publisher.objects.filter(name__iexact=name).exists():
            messages.error(
                request,
                'This publisher already exists.'
            )

        else:
            try:
                with transaction.atomic():

                    publisher = Publisher.objects.create(
                        name=name,
                        description=description
                    )

                    request.user.editor_publishers.add(publisher)

                messages.success(
                    request,
                    f'{publisher.name} created successfully.'
                )

                return redirect('editor_dashboard')

            except Exception as error:
                logger.error(
                    'Publisher creation failed: %s',
                    error
                )

                messages.error(
                    request,
                    'There was a problem creating the publisher.'
                )

    return render(
        request,
        'good_to_know/publisher_form.html',
        {
            'page_title': 'Create Publisher',
        }
    )


# Journalist article and newsletter management
# =============================================
#
# Journalists can create, edit and delete their own articles and
# newsletters.
#
# Independent journalists can self-approve their publications because
# they are not affiliated with a publisher. Publications associated
# with a publisher require editorial approval.
#
# Article and newsletter management functions are separated according
# to user role. This approach simplifies permission allocation and
# supports the implementation of additional functionality, including
# API endpoints.


# Create article
# --------------
@login_required
@user_passes_test(is_journalist)
def create_article(request):
    """Create a new article.

    Allows authenticated journalists to create articles using the
    article submission form.

    Articles can be submitted independently or associated with a
    publisher. Articles associated with a publisher require editorial
    approval, whereas independent articles are automatically approved.

    Following successful submission, the journalist is redirected
    to their dashboard.

    :param request: The HTTP request received from the authenticated
        journalist.
    :type request: HttpRequest
    :returns: A redirect response following successful article creation,
        or a rendered response containing the article submission form.
    :rtype: HttpResponse
    """

    if request.method == 'POST':

        form = ArticleForm(
            request.POST or None,
            request.FILES or None,
            user=request.user
        )

        if form.is_valid():

            article = form.save(commit=False)

            article.author = request.user
            if article.publisher:
                article.approved = False
            else:
                article.approved = True

            article.save()

            messages.success(
                request,
                'Article created successfully.'
            )

            return redirect('journalist_dashboard')

    else:

        form = ArticleForm(user=request.user)

    return render(
        request,
        'good_to_know/article_form.html',
        {
            'form': form,
            'page_title': 'Create Article',
        }
    )


# Journalist edit article
# -----------------------
@login_required
@user_passes_test(is_journalist)
def edit_article(request, article_id):
    """Edit an existing article.

    Allows authenticated journalists to edit articles that they have
    authored. The article is retrieved using its unique identifier
    and the authenticated user's ownership.

    Edited articles associated with a publisher require fresh
    editorial approval. Independently published articles remain
    automatically approved.

    Following a successful update, the journalist is redirected
    to their dashboard.

    :param request: The HTTP request received from the authenticated
        journalist.
    :type request: HttpRequest
    :param article_id: The unique identifier of the article to edit.
    :type article_id: int
    :returns: A redirect response following a successful update, or
        a rendered response containing the article editing form.
    :rtype: HttpResponse
    """
    article = get_object_or_404(
        Article,
        id=article_id,
        author=request.user
    )

    form = ArticleForm(
        request.POST or None,
        request.FILES or None,
        instance=article
    )
    form.fields['publisher'].queryset = request.user.publishers.all()

    if request.method == 'POST':

        if form.is_valid():

            article = form.save(commit=False)

            # Changes require fresh approval.
            if article.publisher:
                article.approved = False
            else:
                article.approved = True

            article.save()

            messages.success(
                request,
                'Article updated successfully.'
            )

            return redirect('journalist_dashboard')

    return render(
        request,
        'good_to_know/article_form.html',
        {
            'form': form,
            'page_title': 'Edit Article',
        }
    )


# Delete article
# --------------
@login_required
@user_passes_test(is_journalist)
@require_POST
def delete_article(request, article_id):
    """Delete an existing article.

    Allows authenticated journalists to delete articles that they
    have authored. The article is retrieved using its unique
    identifier and the authenticated user's ownership.

    The deletion operation is restricted to POST requests.
    Following successful deletion, a confirmation message is
    displayed and the journalist is redirected to their dashboard.

    :param request: The HTTP POST request received from the
        authenticated journalist.
    :type request: HttpRequest
    :param article_id: The unique identifier of the article to delete.
    :type article_id: int
    :returns: A redirect response to the journalist dashboard.
    :rtype: HttpResponseRedirect
    """

    article = get_object_or_404(
        Article,
        id=article_id,
        author=request.user
    )

    article.delete()

    messages.success(
        request,
        'Article deleted successfully.'
    )

    return redirect('journalist_dashboard')


# Journalist create newsletter
# -----------------------------
@login_required
@user_passes_test(is_journalist)
def create_newsletter(request):
    """Create a new newsletter.

    Allows authenticated journalists to create newsletters using
    the newsletter submission form.

    Both independent journalists and journalists affiliated with
    publishers can create newsletters using their own articles.
    Newsletters associated with a publisher require editorial
    approval, whereas independent newsletters are automatically
    approved.

    Newsletter creation and the association of articles are
    performed within an atomic database transaction.

    Following successful creation, the journalist is redirected
    to the newsletter detail page. If an exception occurs during
    creation, an error message is displayed.

    :param request: The HTTP request received from the authenticated
        journalist.
    :type request: HttpRequest
    :returns: A redirect response following successful newsletter
        creation, or a rendered response containing the newsletter
        submission form.
    :rtype: HttpResponse
    """

    if request.method == 'POST':

        form = NewsletterForm(
            request.POST,
            user=request.user
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    newsletter = form.save(commit=False)
                    newsletter.author = request.user

                    newsletter.publisher = form.cleaned_data['publisher']

                    if newsletter.publisher:
                        newsletter.approved = False
                    else:
                        newsletter.approved = True

                    newsletter.save()
                    form.save_m2m()

                    messages.success(
                        request,
                        'Newsletter created successfully.'
                    )

                    return redirect('newsletter_detail',
                                    newsletter_id=newsletter.id)
            except Exception as e:
                messages.error(request,
                               f'Problem creating this newsletter: {e}'
                               'Please try again.')
    else:
        form = NewsletterForm(user=request.user)

    return render(
        request,
        'good_to_know/newsletter_form.html',
        {
            'form': form,
            'page_title': 'Create Newsletter',
        }
    )


# Journalist edit newsletter
# --------------------------
@login_required
@user_passes_test(is_journalist)
def edit_newsletter(request, newsletter_id):
    """Edit an existing newsletter.

    Allows authenticated journalists to edit newsletters that they
    have authored. The newsletter is retrieved using its unique
    identifier and the authenticated user's ownership.

    Newsletters associated with a publisher require fresh editorial
    approval following an update. Independent newsletters remain
    automatically approved.

    Following a successful update, the journalist is redirected
    to their dashboard.

    :param request: The HTTP request received from the authenticated
        journalist.
    :type request: HttpRequest
    :param newsletter_id: The unique identifier of the newsletter
        to edit.
    :type newsletter_id: int
    :returns: A redirect response following a successful update,
        or a rendered response containing the newsletter editing form.
    :rtype: HttpResponse
    """

    newsletter = get_object_or_404(
        Newsletter,
        id=newsletter_id,
        author=request.user
    )

    form = NewsletterForm(
        request.POST or None,
        instance=newsletter,
        user=request.user
    )

    if request.method == 'POST':

        if form.is_valid():

            newsletter = form.save(commit=False)

            if newsletter.publisher:
                newsletter.approved = False
            else:
                newsletter.approved = True

            newsletter.save()
            form.save_m2m()

            messages.success(
                request,
                'Newsletter updated successfully.'
            )

            return redirect('journalist_dashboard')

    return render(
        request,
        'good_to_know/newsletter_form.html',
        {
            'form': form,
            'page_title': 'Edit Newsletter',
        }
    )


# Journalist delete newsletter
# ----------------------------
@login_required
@user_passes_test(is_journalist)
@require_POST
def delete_newsletter(request, newsletter_id):
    """Delete an existing newsletter.

    Allows authenticated journalists to delete newsletters that
    they have authored. The newsletter is retrieved using its
    unique identifier and the authenticated user's ownership.

    The deletion operation is restricted to POST requests.
    Following successful deletion, a confirmation message is
    displayed and the journalist is redirected to their dashboard.

    :param request: The HTTP POST request received from the
        authenticated journalist.
    :type request: HttpRequest
    :param newsletter_id: The unique identifier of the newsletter
        to delete.
    :type newsletter_id: int
    :returns: A redirect response to the journalist dashboard.
    :rtype: HttpResponseRedirect
    """

    newsletter = get_object_or_404(
        Newsletter,
        id=newsletter_id,
        author=request.user
    )

    newsletter.delete()

    messages.success(
        request,
        'Newsletter deleted successfully.'
    )

    return redirect('journalist_dashboard')


# Editor article management
# =========================
#
# Article and newsletter affiliation with an editor's publisher is
# established to support efficient filtering and permission checks.
#
# Editors are responsible for editing, approving and deleting
# publications. In accordance with the application requirements,
# publication creation is restricted to journalists.
#
# Once publications have been approved, they are distributed to
# subscribers by email. For the purposes of this application,
# email output is also displayed in the console.


# Content filter
# --------------
def editor_articles(user):
    """Retrieve articles associated with an editor's publishers.

    Filters articles according to the publishers assigned to the
    specified editor. This function supports the editor dashboard
    and other editor-specific publication management operations.

    A permission exception is raised if the editor has no assigned
    publishers.

    :param user: The editor whose associated publishers are used
        to filter the articles.
    :type user: CustomUser
    :raises PermissionDenied: If the editor has no assigned publisher.
    :returns: A queryset containing articles associated with the
        editor's publishers.
    :rtype: QuerySet
    """

    publishers = user.editor_publishers.all()

    if not publishers.exists():
        raise PermissionDenied(
            'Your editor account has no assigned publisher.'
        )

    return Article.objects.filter(
        publisher__in=publishers
    )


def editor_newsletters(user):
    """Retrieve newsletters associated with an editor's publishers.

    Filters newsletters according to the publishers assigned to the
    specified editor. This function supports newsletter filtering
    and editor-specific publication management.

    A permission exception is raised if the editor has no assigned
    publishers.

    :param user: The editor whose associated publishers are used
        to filter the newsletters.
    :type user: CustomUser
    :raises PermissionDenied: If the editor has no assigned publisher.
    :returns: A queryset containing newsletters associated with
        the editor's publishers.
    :rtype: QuerySet
    """

    publishers = user.editor_publishers.all()

    if not publishers.exists():
        raise PermissionDenied(
            'Your editor account has no assigned publisher.'
        )

    # Only newsletters containing articles from this publisher.
    # Exclude newsletters containing articles from other publishers.
    return Newsletter.objects.filter(
        publisher__in=publishers
    )


# Editor edit article
# -------------------
@login_required
@user_passes_test(is_editor)
def editor_edit_article(request, article_id):
    """Edit an article associated with an editor's publisher.

    Allows authenticated editors to edit articles associated with
    their assigned publishers.

    The article is retrieved using its unique identifier and the
    editor's associated publishers. The publisher selection field
    is restricted to publishers assigned to the authenticated editor.

    Following a successful update, the article is marked as pending
    approval and the editor is redirected to the editor dashboard.

    :param request: The HTTP request received from the authenticated
        editor.
    :type request: HttpRequest
    :param article_id: The unique identifier of the article to edit.
    :type article_id: int
    :returns: A redirect response following a successful update,
        or a rendered response containing the article editing form.
    :rtype: HttpResponse
    """

    article = get_object_or_404(
        editor_articles(request.user),
        id=article_id
    )

    form = ArticleForm(
        request.POST or None,
        request.FILES or None,
        instance=article,
        user=request.user
    )
    form.fields['publisher'].queryset = (
        request.user.editor_publishers.all()
    )

    if request.method == 'POST':

        if form.is_valid():
            article = form.save(commit=False)
            article.approved = False
            article.save()

            messages.success(
                request,
                'Article updated successfully.'
            )

            return redirect('editor_dashboard')

    return render(
        request,
        'good_to_know/article_form.html',
        {
            'form': form,
            'page_title': 'Edit Article',
        }
    )


# Delete article editor
# ---------------------
@login_required
@user_passes_test(is_editor)
@require_POST
def editor_delete_article(request, article_id):
    """Delete an article associated with an editor's publisher.

    Allows authenticated editors to delete articles associated
    with their assigned publishers.

    The article is retrieved using its unique identifier and the
    editor's associated publishers. Deletion is restricted to
    POST requests.

    Following successful deletion, a confirmation message is
    displayed and the editor is redirected to the editor dashboard.

    :param request: The HTTP POST request received from the
        authenticated editor.
    :type request: HttpRequest
    :param article_id: The unique identifier of the article to delete.
    :type article_id: int
    :returns: A redirect response to the editor dashboard.
    :rtype: HttpResponseRedirect
    """

    article = get_object_or_404(
        editor_articles(request.user),
        id=article_id
    )

    article.delete()

    messages.success(
        request,
        'Article deleted successfully.'
    )

    return redirect('editor_dashboard')


# Editor approve article
# ----------------------
@login_required
@user_passes_test(is_editor)
@require_POST
def approve_article(request, article_id):
    """Approve an article and initiate its distribution.

    Allows authenticated editors to approve articles associated
    with their assigned publishers.

    Once approved, the article is saved and the distribution
    process is initiated. Approved articles are distributed
    to subscribers by email and submitted to the approved articles
    API.

    If distribution fails, the error is recorded in the application
    log and a warning message is displayed. The article remains
    approved even if distribution encounters a problem.

    The approval operation is restricted to POST requests.

    :param request: The HTTP POST request received from the
        authenticated editor.
    :type request: HttpRequest
    :param article_id: The unique identifier of the article to approve.
    :type article_id: int
    :returns: A redirect response to the editor dashboard.
    :rtype: HttpResponseRedirect
    """

    article = get_object_or_404(
        editor_articles(request.user),
        id=article_id
    )

    article.approved = True
    article.save(update_fields=['approved'])

    messages.success(
        request,
        'Article approved successfully.'
    )

    try:
        distribute_approved_article(article, request)

        messages.success(
            request,
            'Article distributed to subscribers and API.'
        )

    except Exception as error:
        logger.error(
            'Article distribution failed: %s',
            error
        )

        messages.warning(
            request,
            'Article approved, but distribution encountered a problem.'
        )

    return redirect('editor_dashboard')


# Editor approve newsletter
# -------------------------
@login_required
@user_passes_test(is_editor)
@require_POST
def approve_newsletter(request, newsletter_id):
    """Approve a newsletter associated with an editor's publisher.

    Allows authenticated editors to approve newsletters associated
    with their assigned publishers.

    The newsletter approval status is updated and saved to the
    database. Following successful approval, a confirmation
    message is displayed and the editor is redirected to the
    editor dashboard.

    The approval operation is restricted to POST requests.

    :param request: The HTTP POST request received from the
        authenticated editor.
    :type request: HttpRequest
    :param newsletter_id: The unique identifier of the newsletter
        to approve.
    :type newsletter_id: int
    :returns: A redirect response to the editor dashboard.
    :rtype: HttpResponseRedirect
    """

    newsletter = get_object_or_404(
        editor_newsletters(request.user),
        id=newsletter_id
    )

    newsletter.approved = True
    newsletter.save(update_fields=['approved'])

    messages.success(
        request,
        'Newsletter approved successfully.'
    )

    return redirect('editor_dashboard')


# Distribute approved article
# ---------------------------
def distribute_approved_article(article, request):
    """Distribute an approved article to subscribers and the API.

    Checks whether the article has been approved before initiating
    distribution. Approved articles are distributed to readers
    subscribed to the article's publisher and journalist.

    Subscriber email addresses are collected and used to send an
    email containing the article as an HTML attachment.

    The approved article is also submitted to the application's
    approved articles API using token authentication.

    If the article has not been approved, the function returns
    without performing any distribution operations.

    :param article: The article to distribute to subscribers and
        the approved articles API.
    :type article: Article
    :param request: The HTTP request used to construct the API
        endpoint URL and obtain the authenticated user's token.
    :type request: HttpRequest
    :returns: None.
    :rtype: None
    :raises requests.exceptions.RequestException: If the API request
        fails or returns an unsuccessful HTTP status code.
    :raises Exception: If an error occurs during email generation,
        delivery or API distribution.
    """

    if not article.approved:
        return

    # Collect publisher subscribers.
    publisher_subscribers = (
        article.publisher.subscribers.all()
        if article.publisher else CustomUser.objects.none()
    )

    # Collect journalist subscribers.
    journalist_subscribers = (
        article.author.journalist_subscribers.filter(
            role=CustomUser.Role.READER
        )
    )

    # Combine subscriber querysets and remove duplicate users.
    subscribers = (
        publisher_subscribers | journalist_subscribers
    ).distinct()

    # Collect email addresses for subscribers with valid addresses.
    recipient_emails = [
        subscriber.email
        for subscriber in subscribers
        if subscriber.email
    ]

    # Send subscriber email.
    if recipient_emails:

        subscriber_html = render_to_string(
            'good_to_know/article_subscriber.html',
            {'article': article}
        )

        email = EmailMessage(
            subject=f'New article from {article.author}',
            body='Thank you for subscribing to Good To Know.',
            from_email=None,
            to=recipient_emails
        )

        email.attach(
            f'article_{article.id}.html',
            subscriber_html,
            'text/html'
        )

        email.send(fail_silently=False)

    # POST approved article to own API.
    token, created = Token.objects.get_or_create(
        user=request.user
    )

    response = requests.post(
        request.build_absolute_uri(
            reverse_lazy('api_approved_article')
        ),
        json={'article_id': article.id},
        headers={
            'Authorization': f'Token {token.key}'
        },
        timeout=10
    )

    response.raise_for_status()


# Edit newsletter update
# ----------------------
@login_required
@user_passes_test(is_editor)
def editor_edit_newsletter(request, newsletter_id):
    """Edit an existing newsletter associated with an editor's publisher.

    Allows authenticated editors to edit newsletters associated
    with their assigned publishers.

    The newsletter is retrieved using its unique identifier and
    the editor's associated publishers. The article selection field
    is restricted to approved articles belonging to the newsletter's
    publisher.

    Following a successful update, the newsletter is marked as
    pending approval. The updated newsletter and its associated
    articles are saved, and the editor is redirected to the
    editor dashboard.

    :param request: The HTTP request received from the authenticated
        editor.
    :type request: HttpRequest
    :param newsletter_id: The unique identifier of the newsletter
        to edit.
    :type newsletter_id: int
    :returns: A redirect response following a successful update,
        or a rendered response containing the newsletter editing form.
    :rtype: HttpResponse
    """

    newsletter = get_object_or_404(
        editor_newsletters(request.user),
        id=newsletter_id
    )

    form = NewsletterForm(
        request.POST or None,
        instance=newsletter,
        user=request.user
    )
    form.fields['articles'].queryset = (
        Article.objects.filter(
            publisher=newsletter.publisher,
            approved=True
        )
    )

    if request.method == 'POST':

        if form.is_valid():

            newsletter = form.save(commit=False)
            newsletter.approved = False
            newsletter.save()
            form.save_m2m()

            messages.success(
                request,
                'Newsletter updated successfully.'
            )

            return redirect('editor_dashboard')

    return render(
        request,
        'good_to_know/newsletter_form.html',
        {
            'form': form,
            'page_title': 'Edit Newsletter',
        }
    )


# Editor delete newsletter
# ------------------------
@login_required
@user_passes_test(is_editor)
@require_POST
def editor_delete_newsletter(request, newsletter_id):
    """Delete a newsletter associated with an editor's publisher.

    Allows authenticated editors to delete newsletters associated
    with their assigned publishers.

    The newsletter is retrieved using its unique identifier and
    the editor's associated publishers. Deletion is restricted
    to POST requests.

    Following successful deletion, a confirmation message is
    displayed and the editor is redirected to the editor dashboard.

    :param request: The HTTP POST request received from the
        authenticated editor.
    :type request: HttpRequest
    :param newsletter_id: The unique identifier of the newsletter
        to delete.
    :type newsletter_id: int
    :returns: A redirect response to the editor dashboard.
    :rtype: HttpResponseRedirect
    """

    newsletter = get_object_or_404(
        editor_newsletters(request.user),
        id=newsletter_id
    )

    newsletter.delete()

    messages.success(
        request,
        'Newsletter deleted successfully.'
    )

    return redirect('editor_dashboard')


# Subscription
# =============
#
# Readers can manage their subscriptions to publishers and journalists
# through the application.
#
# Subscription functionality is available to authenticated readers
# and is presented through the relevant browsing pages.
#
# Journalist and editor accounts are excluded from this functionality.
# Subscription relationships are maintained through the user's
# subscription associations.


# Subscribe to publisher
# ----------------------
@login_required
@user_passes_test(is_reader)
@require_POST
def subscribe_publisher(request, publisher_id):
    """Subscribe a reader to a publisher.

    Allows authenticated readers to subscribe to publishers.

    The publisher is retrieved using its unique identifier and
    added to the authenticated reader's subscribed publishers.
    A confirmation message is displayed following successful
    subscription.

    The operation is restricted to POST requests and is only
    available to authenticated users with the reader role.

    :param request: The HTTP POST request received from the
        authenticated reader.
    :type request: HttpRequest
    :param publisher_id: The unique identifier of the publisher
        to subscribe to.
    :type publisher_id: int
    :returns: A redirect response to the reader dashboard.
    :rtype: HttpResponseRedirect
    """

    publisher = get_object_or_404(
        Publisher,
        id=publisher_id
    )

    request.user.subscribed_publishers.add(publisher)

    messages.success(
        request,
        f"You have subscribed to {publisher.name}."
    )

    return redirect("reader_dashboard")


# Un-subscribe from publisher
# ---------------------------
@login_required
@user_passes_test(is_reader)
@require_POST
def unsubscribe_publisher(request, publisher_id):
    """Unsubscribe a reader from a publisher.

    Allows authenticated readers to unsubscribe from publishers
    to which they have previously subscribed.

    The publisher is retrieved using its unique identifier and
    removed from the authenticated reader's subscribed publishers.
    A confirmation message is displayed following successful
    unsubscription.

    The operation is restricted to POST requests and is only
    available to authenticated users with the reader role.

    :param request: The HTTP POST request received from the
        authenticated reader.
    :type request: HttpRequest
    :param publisher_id: The unique identifier of the publisher
        to unsubscribe from.
    :type publisher_id: int
    :returns: A redirect response to the reader dashboard.
    :rtype: HttpResponseRedirect
    """

    publisher = get_object_or_404(
        Publisher,
        id=publisher_id
    )

    request.user.subscribed_publishers.remove(publisher)

    messages.success(
        request,
        f"You have unsubscribed from {publisher.name}."
    )

    return redirect("reader_dashboard")


# Subscribe to journalist
# -----------------------
@login_required
@user_passes_test(is_reader)
@require_POST
def subscribe_journalist(request, journalist_id):
    """Subscribe a reader to a journalist.

    Allows authenticated readers to subscribe to journalists.

    The journalist is retrieved using their unique identifier,
    with an additional check to ensure that the account has the
    journalist role. The journalist is then added to the
    authenticated reader's subscribed journalists.

    A confirmation message is displayed following successful
    subscription.

    The operation is restricted to POST requests and is only
    available to authenticated users with the reader role.

    :param request: The HTTP POST request received from the
        authenticated reader.
    :type request: HttpRequest
    :param journalist_id: The unique identifier of the journalist
        to subscribe to.
    :type journalist_id: int
    :returns: A redirect response to the home page.
    :rtype: HttpResponseRedirect
    """

    journalist = get_object_or_404(
        CustomUser,
        id=journalist_id,
        role=CustomUser.Role.JOURNALIST
    )

    request.user.subscribed_journalists.add(journalist)

    messages.success(
        request,
        f"You have subscribed to {journalist.username}."
    )

    return redirect("home")


# Un-subscribe from journalist
# ----------------------------
@login_required
@user_passes_test(is_reader)
@require_POST
def unsubscribe_journalist(request, journalist_id):
    """Unsubscribe a reader from a journalist.

    Allows authenticated readers to unsubscribe from journalists
    to which they have previously subscribed.

    The journalist is retrieved using their unique identifier,
    with an additional check to ensure that the account has the
    journalist role. The journalist is then removed from the
    authenticated reader's subscribed journalists.

    A confirmation message is displayed following successful
    unsubscription.

    The operation is restricted to POST requests and is only
    available to authenticated users with the reader role.

    :param request: The HTTP POST request received from the
        authenticated reader.
    :type request: HttpRequest
    :param journalist_id: The unique identifier of the journalist
        to unsubscribe from.
    :type journalist_id: int
    :returns: A redirect response to the reader dashboard.
    :rtype: HttpResponseRedirect
    """

    journalist = get_object_or_404(
        CustomUser,
        id=journalist_id,
        role=CustomUser.Role.JOURNALIST
    )

    request.user.subscribed_journalists.remove(journalist)

    messages.success(
        request,
        f"You have unsubscribed from {journalist.username}."
    )

    return redirect("reader_dashboard")


# Browse functions
# ================
#
# The following functions allow users to browse articles, journalists,
# publishers and newsletters across the application.
#
# This functionality provides access to publications throughout the
# database, whereas individual user dashboards are restricted to
# publications associated with their respective accounts or roles.


# Browse publishers
# -----------------
def browse_publishers(request):
    """Display all publishers available in the application.

    Retrieves all publishers from the database and orders them
    alphabetically by name.

    For authenticated readers, the IDs of publishers to which
    they have subscribed are also retrieved. This information
    allows the browsing template to identify existing subscriptions.

    :param request: The HTTP request received from the user.
    :type request: HttpRequest
    :returns: A rendered response containing the publisher list
        and the authenticated reader's subscription information.
    :rtype: HttpResponse
    """

    publishers = Publisher.objects.all().order_by('name')
    subscribed_publisher_ids = []

    if request.user.is_authenticated and is_reader(request.user):
        subscribed_publisher_ids = list(
            request.user.subscribed_publishers.values_list(
                'id',
                flat=True
            )
        )

    return render(
        request,
        'good_to_know/browse_publishers.html',
        {
            'publishers': publishers,
            'subscribed_publisher_ids': subscribed_publisher_ids,
        }
    )


# Browse journalists
# -------------------
def browse_journalists(request):
    """Display all journalists registered in the application.

    Retrieves users assigned the journalist role and orders
    the results alphabetically by username.

    For authenticated readers, the IDs of journalists to whom
    they have subscribed are also retrieved. This information
    allows the browsing template to identify existing subscriptions.

    :param request: The HTTP request received from the user.
    :type request: HttpRequest
    :returns: A rendered response containing the journalist list
        and the authenticated reader's subscription information.
    :rtype: HttpResponse
    """

    journalists = User.objects.filter(
        role=CustomUser.Role.JOURNALIST
    ).order_by('username')

    subscribed_journalist_ids = []

    if request.user.is_authenticated and is_reader(request.user):
        subscribed_journalist_ids = list(
            request.user.subscribed_journalists.values_list(
                'id',
                flat=True
            )
        )
    return render(
        request,
        'good_to_know/browse_journalists.html',
        {
            'journalists': journalists,
            'subscribed_ids': subscribed_journalist_ids,
        }
    )


# Collections
# ===========
#
# Collection views group publications according to their associated
# publishers or journalists.
#
# This functionality supports the browsing system and allows readers
# to explore publications from individual publishers and journalists.
# Collections also provide a structured way to display articles and
# newsletters together with their associated authors and publishers.


# Publisher collection
# --------------------
def publisher_collection(request, publisher_id):
    """Display the approved publications associated with a publisher.

    Retrieves a publisher using its unique identifier and displays
    its approved articles, approved newsletters and associated
    journalists.

    Articles are ordered by creation date, with the most recent
    displayed first. Newsletters are also ordered by creation date
    and include their associated articles.

    Journalists associated with the publisher are ordered
    alphabetically by username.

    :param request: The HTTP request received from the user.
    :type request: HttpRequest
    :param publisher_id: The unique identifier of the publisher
        whose collection is being displayed.
    :type publisher_id: int
    :returns: A rendered response containing the publisher's
        approved publications and associated journalists.
    :rtype: HttpResponse
    """

    publisher = get_object_or_404(
        Publisher,
        id=publisher_id
    )

    articles = Article.objects.filter(
        publisher=publisher,
        approved=True
    ).select_related(
        'author'
    ).order_by('-created_at')

    newsletters = Newsletter.objects.filter(
        publisher=publisher,
        approved=True
    ).prefetch_related(
        'articles'
    ).order_by('-created_at')

    journalists = CustomUser.objects.filter(
        role=CustomUser.Role.JOURNALIST,
        publishers=publisher
    ).order_by('username')

    return render(
        request,
        'good_to_know/publisher_collection.html',
        {
            'publisher': publisher,
            'articles': articles,
            'newsletters': newsletters,
            'journalists': journalists,
        }
    )


# Journalist collection
# --------------------
def journalist_collection(request, journalist_id):
    """Display the approved publications associated with a journalist.

    Retrieves a journalist using their unique identifier and verifies
    that the account has the journalist role.

    Displays the journalist's approved articles and newsletters.
    Both publication types are ordered by creation date, with the
    most recent publications displayed first. Newsletters include
    their associated articles.

    :param request: The HTTP request received from the user.
    :type request: HttpRequest
    :param journalist_id: The unique identifier of the journalist
        whose collection is being displayed.
    :type journalist_id: int
    :returns: A rendered response containing the journalist's
        approved articles and newsletters.
    :rtype: HttpResponse
    """

    journalist = get_object_or_404(
        CustomUser,
        id=journalist_id,
        role=CustomUser.Role.JOURNALIST
    )

    articles = Article.objects.filter(
        author=journalist,
        approved=True
    ).order_by('-created_at')

    newsletters = Newsletter.objects.filter(
        author=journalist,
        approved=True
    ).prefetch_related(
        'articles'
    ).order_by('-created_at')

    return render(
        request,
        'good_to_know/journalist_collection.html',
        {
            'journalist': journalist,
            'articles': articles,
            'newsletters': newsletters,
        }
    )


# Browse newsletters
# ------------------
def browse_newsletters(request):
    """Display all approved newsletters in the application.

    Retrieves newsletters that have received editorial approval
    and orders them by creation date, with the most recent
    newsletters displayed first.

    :param request: The HTTP request received from the user.
    :type request: HttpRequest
    :returns: A rendered response containing the approved newsletter list.
    :rtype: HttpResponse
    """

    newsletters = Newsletter.objects.filter(
        approved=True
    ).order_by('-created_at')

    return render(
        request,
        'good_to_know/browse_newsletters.html',
        {
            'newsletters': newsletters,
        }
    )


# Browse articles
# ---------------
def browse_articles(request):
    """Display all approved articles in the application.

    Retrieves articles that have received editorial approval
    and orders them by creation date, with the most recent
    articles displayed first.

    :param request: The HTTP request received from the user.
    :type request: HttpRequest
    :returns: A rendered response containing the approved article list.
    :rtype: HttpResponse
    """

    articles = Article.objects.filter(
        approved=True
    ).order_by('-created_at')

    return render(
        request,
        'good_to_know/browse_articles.html',
        {
            'articles': articles,
        }
    )


# API Functions
# =============
#
# The following functions provide supporting functionality for the
# application's REST API.
#
# They handle role-based access restrictions, publisher assignment
# checks, model validation and the retrieval of articles submitted
# through API requests.


# Get reader
# ----------
def api_get_reader(user):
    """Validate that the authenticated user has the reader role.

    Checks whether the supplied user account has the reader role.
    If the user has a different role, a REST framework permission
    exception is raised.

    :param user: The authenticated user whose role is being checked.
    :type user: CustomUser
    :raises DRFPermissionDenied: If the user does not have the reader role.
    :returns: The authenticated reader account.
    :rtype: CustomUser
    """
    if user.role != CustomUser.Role.READER:
        raise DRFPermissionDenied(
            "Only readers can access this endpoint."
        )

    return user


# Get journalist
# --------------
def api_get_journalist(user):
    """Validate that the authenticated user has the journalist role.

    Checks whether the supplied user account has the journalist role.
    If the user has a different role, a REST framework permission
    exception is raised.

    :param user: The authenticated user whose role is being checked.
    :type user: CustomUser
    :raises DRFPermissionDenied: If the user does not have the
        journalist role.
    :returns: The authenticated journalist account.
    :rtype: CustomUser
    """

    if user.role != CustomUser.Role.JOURNALIST:
        raise DRFPermissionDenied(
            "Only journalists can access this endpoint."
        )

    return user


# Get editor publisher
# --------------------
def api_get_editor_publisher(user):
    """Retrieve the publishers assigned to an authenticated editor.

    Checks whether the supplied user account has the editor role
    and retrieves the publishers associated with that account.

    A permission exception is raised if the user does not have
    the editor role or has no assigned publishers.

    :param user: The authenticated user whose editor role and
        publisher associations are being checked.
    :type user: CustomUser
    :raises DRFPermissionDenied: If the user is not an editor or
        has no assigned publisher.
    :returns: A queryset containing the editor's assigned publishers.
    :rtype: QuerySet
    """

    if user.role != CustomUser.Role.EDITOR:
        raise DRFPermissionDenied(
            "Only editors can access this endpoint."
        )
    publishers = user.editor_publishers.all()

    if not publishers.exists():
        raise DRFPermissionDenied(
            "Your editor account has no assigned publisher."
        )

    return publishers


# Validate model
# --------------
def api_validate_model(instance):
    """Validate a Django model instance and return validation errors.

    Runs Django's full model validation using the ``full_clean()``
    method. If validation fails, the resulting Django validation
    errors are converted into Django REST framework validation
    exceptions for consistent API error handling.

    :param instance: The Django model instance to validate.
    :type instance: Model
    :raises ValidationError: If the model instance fails validation.
    :returns: None.
    :rtype: None
    """

    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        instance.full_clean()
    except DjangoValidationError as error:
        raise ValidationError(
            getattr(error, 'message_dict', error.messages)
        )


# Get articles
# ------------
def api_get_articles(request, **filters):
    """Retrieve and validate articles submitted through an API request.

    Retrieves article IDs from the request data and validates that
    they are supplied as a list without duplicate entries.

    Articles are retrieved from the database using the supplied IDs
    and any additional filtering criteria. A validation exception
    is raised if the number of retrieved articles does not match
    the number of submitted IDs.

    :param request: The API request containing the submitted article IDs.
    :type request: Request
    :param filters: Additional filtering criteria applied to the
        article database query.
    :type filters: dict
    :raises ValidationError: If the article IDs are not supplied as
        a list, contain duplicates, or include unavailable articles.
    :returns: A queryset containing the validated articles.
    :rtype: QuerySet
    """

    article_ids = request.data.get('articles', [])

    if not isinstance(article_ids, list):
        raise ValidationError(
            "Articles must be supplied as a list of IDs."
        )

    if len(article_ids) != len(set(article_ids)):
        raise ValidationError(
            "Duplicate article IDs are not allowed."
        )

    articles = Article.objects.filter(
        id__in=article_ids,
        **filters
    )

    if articles.count() != len(article_ids):
        raise ValidationError(
            "One or more selected articles are unavailable."
        )

    return articles


# Retrieve and create articles
# ----------------------------
# Authenticated users can retrieve approved articles through the API.
# Article creation is restricted to authenticated journalists.
# Publisher-affiliated articles require editorial approval, whereas
# independently published articles are automatically approved.

# Readers retrieve articles, journalists may create articles
@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_articles(request):
    """Retrieve approved articles or create a new article.

    Provides two API operations depending on the HTTP request method.

    * ``GET``: Retrieves all approved articles, including their
      associated authors and publishers. Articles are ordered by
      creation date, with the most recent displayed first.
    * ``POST``: Allows authenticated journalists to create articles.
      The submitted article is validated using the article serializer
      and Django model validation.

    Articles associated with a publisher require editorial approval.
    Independent articles are automatically approved. Journalists
    can only submit articles associated with publishers to which
    they belong.

    Article creation is performed within an atomic database
    transaction.

    Authentication is provided through token authentication.

    :param request: The authenticated API request containing the
        HTTP method and, for POST requests, the submitted article data.
    :type request: Request
    :raises DRFPermissionDenied: If the authenticated user is not
        a journalist when submitting an article, or if the journalist
        does not belong to the selected publisher.
    :returns: A REST framework response containing serialized article
        data, serializer validation errors, or the created article.
    :rtype: Response
    """

    if request.method == 'GET':

        articles = Article.objects.filter(
            approved=True
        ).select_related(
            'author',
            'publisher'
        ).order_by('-created_at')

        serializer = ArticleSerializer(
            articles,
            many=True
        )

        return Response(serializer.data)

    # POST: Only journalists can create articles.
    journalist = api_get_journalist(request.user)

    serializer = ArticleSerializer(data=request.data)

    if serializer.is_valid():

        values = dict(serializer.validated_data)
        values.pop('author', None)
        values.pop('approved', None)

        publisher = values.get('publisher')

        # Checks journalist belongs to selected publisher.
        if publisher and not journalist.publishers.filter(
            id=publisher.id
        ).exists():
            raise DRFPermissionDenied(
                "You do not belong to this publisher."
            )

        article = Article(
            author=journalist,
            approved=False if publisher else True,
            **values
        )

        api_validate_model(article)

        with transaction.atomic():
            article.save()

        return Response(
            ArticleSerializer(article).data,
            status=status.HTTP_201_CREATED
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


# Get subscribed articles
# -----------------------
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_subscribed_articles(request):
    """Retrieve approved articles from a reader's subscriptions.

    Retrieves approved articles written by journalists or published
    by publishers to which the authenticated reader has subscribed.

    The results include associated authors and publishers and are
    ordered by creation date, with the most recent articles displayed
    first. Duplicate results are removed.

    Access is restricted to authenticated users with the reader role.
    Authentication is provided through token authentication.

    :param request: The authenticated API request.
    :type request: Request
    :raises DRFPermissionDenied: If the authenticated user does not
        have the reader role.
    :returns: A REST framework response containing the serialized
        subscribed articles.
    :rtype: Response
    """

    reader = api_get_reader(request.user)

    journalists = reader.subscribed_journalists.all()

    publishers = reader.subscribed_publishers.all()

    articles = Article.objects.filter(
        approved=True
    ).filter(
        Q(author__in=journalists) |
        Q(publisher__in=publishers)
    ).select_related(
        'author',
        'publisher'
    ).distinct().order_by('-created_at')

    serializer = ArticleSerializer(
        articles,
        many=True
    )

    return Response(serializer.data)


# Article details
# ---------------
@api_view(['GET', 'PUT', 'DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_article_detail(request, article_id):
    """Retrieve, update or delete an individual article.

    Provides three API operations depending on the HTTP request method.

    * ``GET``: Retrieves an individual article. Approved articles are
      accessible to all authenticated users. Unapproved articles are
      restricted to their journalist author or an editor associated
      with the article's publisher.
    * ``PUT``: Allows journalists and editors to update articles
      according to their respective permissions. Journalists can only
      update their own articles, whereas editors can update articles
      associated with their assigned publishers.
    * ``DELETE``: Allows journalists to delete their own articles
      and editors to delete articles associated with their assigned
      publishers.

    Journalist updates preserve article ownership and apply the
    appropriate approval status according to publisher affiliation.
    Editor updates preserve publisher ownership and return the article
    to pending approval.

    Model validation is performed before updates are saved.
    Database transactions are used when saving changes.

    Authentication is provided through token authentication.

    :param request: The authenticated API request containing the
        HTTP method and, for PUT requests, the submitted article data.
    :type request: Request
    :param article_id: The unique identifier of the article to retrieve,
        update or delete.
    :type article_id: int
    :raises DRFPermissionDenied: If the authenticated user does not
        have permission to access, update or delete the requested
        article.
    :returns: A REST framework response containing serialized article
        data, a success message, or serializer validation errors.
    :rtype: Response
    """

    article = get_object_or_404(
        Article.objects.select_related(
            'author',
            'publisher'
        ),
        id=article_id
    )

    # GET: Approved articles are available to authenticated users.
    if request.method == 'GET':

        if not article.approved:

            journalist_owner = (
                request.user == article.author
                and is_journalist(request.user)
            )

            editor_owner = (
                is_editor(request.user)
                and article.publisher_id is not None
                and request.user.editor_publishers.filter(
                    id=article.publisher_id
                ).exists()
            )

            if not (journalist_owner or editor_owner):
                raise DRFPermissionDenied(
                    "You cannot access this article."
                )

        serializer = ArticleSerializer(article)

        return Response(serializer.data)

    # PUT: Journalist or editor can update their permitted articles.
    if request.method == 'PUT':

        if is_journalist(request.user):

            journalist = request.user

            if article.author != journalist:
                raise DRFPermissionDenied(
                    "You can only edit your own articles."
                )

            serializer = ArticleSerializer(
                article,
                data=request.data
            )

            if serializer.is_valid():

                values = dict(serializer.validated_data)

                publisher = values.get(
                    'publisher',
                    article.publisher
                )

                if publisher and not journalist.publishers.filter(
                    id=publisher.id
                ).exists():
                    raise DRFPermissionDenied(
                        "You do not belong to this publisher."
                    )

                # Preserve article ownership.
                values.pop('author', None)
                values.pop('approved', None)

                for field, value in values.items():
                    setattr(article, field, value)

                article.approved = (
                    article.publisher is None
                )

                api_validate_model(article)

                with transaction.atomic():
                    article.save()

                return Response(
                    ArticleSerializer(article).data,
                    status=status.HTTP_200_OK
                )

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        elif is_editor(request.user):

            publishers = api_get_editor_publisher(
                request.user
            )

            if article.publisher not in publishers:
                raise DRFPermissionDenied(
                    "You cannot edit this article."
                )

            serializer = ArticleSerializer(
                article,
                data=request.data
            )

            if serializer.is_valid():

                values = dict(serializer.validated_data)

                author = values.pop(
                    'author',
                    article.author
                )

                # Editors cannot change publisher ownership.
                values.pop('publisher', None)
                values.pop('approved', None)

                if not author or not article.publisher.journalists.filter(
                    id=author.id
                ).exists():
                    return Response(
                        {
                            'error': 'Journalist must belong to publisher.'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                for field, value in values.items():
                    setattr(article, field, value)

                article.author = author
                article.approved = False

                api_validate_model(article)

                with transaction.atomic():
                    article.save()

                return Response(
                    ArticleSerializer(article).data,
                    status=status.HTTP_200_OK
                )

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        raise DRFPermissionDenied(
            "Only journalists and editors can edit articles."
        )

    # DELETE: Journalist or editor can delete permitted articles.
    if request.method == 'DELETE':

        if is_journalist(request.user):

            if article.author != request.user:
                raise DRFPermissionDenied(
                    "You can only delete your own articles."
                )

        elif is_editor(request.user):

            publishers = api_get_editor_publisher(
                request.user
            )

            if article.publisher not in publishers:
                raise DRFPermissionDenied(
                    "You cannot delete this article."
                )

        else:
            raise DRFPermissionDenied(
                "You do not have permission to delete articles."
            )

        article.delete()

        return Response(
            {
                'message': 'Article deleted successfully.'
            },
            status=status.HTTP_200_OK
        )


# Get approved articles
# ---------------------
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_approved_article(request):
    """Receive and verify an approved article.

    Retrieves an article using the article ID supplied in the
    API request and verifies that the article has received
    editorial approval.

    If the article exists and is approved, a successful response
    is returned containing its ID and title.

    Access is restricted to authenticated users.
    Authentication is provided through token authentication.

    :param request: The authenticated API request containing
        the article ID.
    :type request: Request
    :returns: A REST framework response containing a confirmation
        message, the article ID and its title.
    :rtype: Response
    :raises Http404: If the article does not exist or has not
        received editorial approval.
    """

    article_id = request.data.get('article_id')

    article = get_object_or_404(
        Article,
        id=article_id,
        approved=True
    )

    return Response(
        {
            'message': 'Approved article received successfully.',
            'article_id': article.id,
            'title': article.title
        },
        status=status.HTTP_201_CREATED
    )


# Newsletter API
# ---------------
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_newsletters(request):
    """Retrieve all approved newsletters.

    Retrieves all newsletters that have received editorial approval.

    The associated authors, publishers and articles are also
    retrieved to support newsletter serialization efficiently.

    Newsletters are ordered by creation date, with the most recent
    displayed first.

    This endpoint is available to all authenticated users,
    regardless of their assigned application role.

    Authentication is provided through token authentication.

    :param request: The authenticated API request.
    :type request: Request
    :returns: A REST framework response containing the serialized
        collection of approved newsletters.
    :rtype: Response
    """

    newsletters = Newsletter.objects.filter(
        approved=True
    ).select_related(
        'author',
        'publisher'
    ).prefetch_related(
        'articles'
    ).order_by('-created_at')

    serializer = NewsletterSerializer(
        newsletters,
        many=True
    )

    return Response(
        serializer.data,
        status=status.HTTP_200_OK
    )


# Get newsletter detail
# ---------------------
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_newsletter_detail(request, newsletter_id):
    """Retrieve an individual newsletter.

    Retrieves a newsletter using its unique identifier, including
    its associated author, publisher and articles.

    Access permissions depend on the newsletter's approval status:

    * Approved newsletters are available to all authenticated users.
    * Unapproved newsletters are restricted to the journalist
      who created them or editors assigned to the newsletter's
      associated publisher.

    If an authenticated user does not meet the access requirements
    for an unapproved newsletter, a REST framework permission
    exception is raised.

    Authentication is provided through token authentication.

    :param request: The authenticated API request.
    :type request: Request
    :param newsletter_id: The unique identifier of the newsletter
        to retrieve.
    :type newsletter_id: int
    :raises DRFPermissionDenied: If the authenticated user does not
        have permission to access an unapproved newsletter.
    :returns: A REST framework response containing the serialized
        newsletter data.
    :rtype: Response
    """

    newsletter = get_object_or_404(
        Newsletter.objects.select_related(
            'author',
            'publisher'
        ).prefetch_related(
            'articles'
        ),
        id=newsletter_id
    )

    if not newsletter.approved:

        journalist_owner = (
            is_journalist(request.user)
            and newsletter.author == request.user
        )

        editor_owner = (
            is_editor(request.user)
            and newsletter.publisher_id is not None
            and request.user.editor_publishers.filter(
                id=newsletter.publisher_id
            ).exists()
        )

        if not (journalist_owner or editor_owner):
            raise DRFPermissionDenied(
                "You cannot access this newsletter."
            )

    serializer = NewsletterSerializer(newsletter)

    return Response(
        serializer.data,
        status=status.HTTP_200_OK
    )


# Editor approve newsletter
# -------------------------
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_approve_newsletter(request, newsletter_id):
    """Approve a newsletter associated with an editor's publisher.

    Allows authenticated editors to approve newsletters belonging
    to publishers assigned to their accounts.

    The newsletter is retrieved using its unique identifier and
    filtered against the editor's assigned publishers.

    Following successful retrieval, the newsletter's approval
    status is updated and saved to the database.

    Access is restricted to authenticated users with the editor role.
    Authentication is provided through token authentication.

    :param request: The authenticated API request.
    :type request: Request
    :param newsletter_id: The unique identifier of the newsletter
        to approve.
    :type newsletter_id: int
    :raises DRFPermissionDenied: If the authenticated user is not
        an editor or does not have an assigned publisher.
    :returns: A REST framework response containing a confirmation
        message, the newsletter ID, its title and approval status.
    :rtype: Response
    """

    publishers = api_get_editor_publisher(request.user)

    newsletter = get_object_or_404(
        Newsletter,
        id=newsletter_id,
        publisher__in=publishers
    )

    newsletter.approved = True

    newsletter.save(
        update_fields=['approved']
    )

    return Response(
        {
            'message': 'Newsletter approved successfully.',
            'newsletter_id': newsletter.id,
            'title': newsletter.title,
            'approved': newsletter.approved
        },
        status=status.HTTP_200_OK
    )


# Get own subscribers
# -------------------
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_users(request):
    """Retrieve readers subscribed to an editor's publisher.

    Allows authenticated editors to retrieve a list of readers
    subscribed to a specified publisher assigned to their account.

    The publisher ID must be supplied as a query parameter.
    The requested publisher is checked against the editor's
    assigned publishers before subscriber information is retrieved.

    Only users with the reader role who are subscribed to the
    specified publisher are included in the results.

    The returned users are ordered alphabetically by username
    and serialized using the user serializer.

    Access is restricted to authenticated users with the editor role.
    Authentication is provided through token authentication.

    :param request: The authenticated API request containing
        the publisher ID as a query parameter.
    :type request: Request
    :raises DRFPermissionDenied: If the authenticated user is not
        an editor, has no assigned publishers, or attempts to
        access a publisher outside their assigned publishers.
    :returns: A REST framework response containing the serialized
        list of subscribed readers or an error message if the
        publisher ID is not supplied.
    :rtype: Response
    """

    if not is_editor(request.user):
        raise DRFPermissionDenied(
            "Only editors can retrieve subscribed users."
        )

    publisher_id = request.query_params.get('publisher_id')

    if not publisher_id:
        return Response(
            {
                'error': 'Please provide a publisher_id.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    publishers = api_get_editor_publisher(request.user)

    publisher = publishers.filter(
        id=publisher_id
    ).first()

    if not publisher:
        raise DRFPermissionDenied(
            "You do not have access to this publisher."
        )

    users = User.objects.filter(
        subscribed_publishers=publisher,
        role=User.Role.READER
    ).order_by('username')

    serializer = UserSerializer(
        users,
        many=True
    )

    return Response(serializer.data)


# List publishers collaborating with news app
# ------------------------------------------
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_publishers(request):
    """Retrieve all publishers registered in the application.

    Retrieves all publishers from the database and orders them
    alphabetically by name.

    The publisher records are serialized using the publisher
    serializer before being returned as an API response.

    This endpoint is available to all authenticated users,
    regardless of their assigned application role.

    Authentication is provided through token authentication.

    :param request: The authenticated API request.
    :type request: Request
    :returns: A REST framework response containing the serialized
        list of publishers.
    :rtype: Response
    """

    publishers = Publisher.objects.all().order_by('name')

    serializer = PublisherSerializer(
        publishers,
        many=True
    )

    return Response(serializer.data)
