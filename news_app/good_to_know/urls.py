
from django.urls import path
from . import views
from .views import RoleBasedLoginView
from rest_framework.authtoken.views import obtain_auth_token


urlpatterns = [

    # Public homepage
    path('', views.welcome, name='welcome'),

    # Registration
    path('register/reader/', views.register_reader, name='register_reader'),
    path('register/journalist/',
         views.register_journalist, name='register_journalist'),
    path('register/editor/', views.register_editor, name='register_editor'),

    path('login/', RoleBasedLoginView.as_view(), name='login'),
    # Authentication
    path('logout/', views.logout_user, name='logout'),

    # User login page
    path('home/', views.home, name='home'),

    # Publication details
    path(
        'article/<int:article_id>/',
        views.article_detail,
        name='article_detail'
    ),

    path(
        'newsletter/<int:newsletter_id>/',
        views.newsletter_detail,
        name='newsletter_detail'
    ),

    # User dashboards
    path(
        'reader-dashboard/',
        views.reader_dashboard,
        name='reader_dashboard'
    ),

    path(
        'journalist/dashboard/',
        views.journalist_dashboard,
        name='journalist_dashboard'
    ),

    # Editor
    path(
        'editor/dashboard/',
        views.editor_dashboard,
        name='editor_dashboard'
    ),
    path(
        'publisher/create/',
        views.create_publisher,
        name='create_publisher'
    ),
    # Journalist article create, update delete urls
    path(
        'journalist/article/create/',
        views.create_article,
        name='create_article'
    ),

    path(
        'journalist/article/<int:article_id>/edit/',
        views.edit_article,
        name='edit_article'
    ),

    path(
        'journalist/article/<int:article_id>/delete/',
        views.delete_article,
        name='delete_article'
    ),

    # Editor article edit and delete, approve functions
    path(
        'editor/article/<int:article_id>/edit/',
        views.editor_edit_article,
        name='editor_edit_article'
    ),

    path(
        'editor/article/<int:article_id>/delete/',
        views.editor_delete_article,
        name='editor_delete_article'
    ),

    path(
        'editor/article/<int:article_id>/approve/',
        views.approve_article,
        name='approve_article'
    ),

    # Editor newsletter edit and delete, approve functions
    path(
        'editor/newsletter/<int:newsletter_id>/edit/',
        views.editor_edit_newsletter,
        name='editor_edit_newsletter'
    ),

    path(
        'editor/newsletter/<int:newsletter_id>/approve/',
        views.approve_newsletter,
        name='approve_newsletter'
    ),

    path(
        'editor/newsletter/<int:newsletter_id>/delete/',
        views.editor_delete_newsletter,
        name='editor_delete_newsletter'
    ),

    # Journalist newsletter create, edit delete functions
    path(
        'journalist/newsletter/create/',
        views.create_newsletter,
        name='create_newsletter'
    ),
    path(
        'journalist/newsletter/<int:newsletter_id>/edit/',
        views.edit_newsletter,
        name='edit_newsletter'
    ),
    path(
        'journalist/newsletter/<int:newsletter_id>/delete/',
        views.delete_newsletter,
        name='delete_newsletter'
    ),

    # Browse links
    path(
        'publishers/',
        views.browse_publishers,
        name='browse_publishers'
        ),

    path(
        'journalists/',
        views.browse_journalists,
        name='browse_journalists'
    ),

    path(
        'newsletters/',
        views.browse_newsletters,
        name='browse_newsletters'
    ),

    path(
        'articles/',
        views.browse_articles,
        name='browse_articles'
    ),

    # Collection links
    path(
        'publisher/<int:publisher_id>/collection/',
        views.publisher_collection,
        name='publisher_collection'
    ),

    path(
        'journalist/<int:journalist_id>/collection/',
        views.journalist_collection,
        name='journalist_collection'
    ),

    # Subscriptions
    path(
        'reader/<int:publisher_id>/subscribe/',
        views.subscribe_publisher,
        name='subscribe_publisher'
    ),

    path(
        'unsubscribe-publisher/<int:publisher_id>/',
        views.unsubscribe_publisher,
        name='unsubscribe_publisher'
    ),

    path(
        'subscribe-journalist/<int:journalist_id>/',
        views.subscribe_journalist,
        name='subscribe_journalist'
    ),

    path(
        'unsubscribe-journalist/<int:journalist_id>/',
        views.unsubscribe_journalist,
        name='unsubscribe_journalist'
    ),

    # API URL patterns
    path(
        'api/token/',
        obtain_auth_token,
        name='api_token'
    ),

    path(
        'api/articles/subscribed/',
        views.api_subscribed_articles,
        name='api_subscribed_articles'
    ),

    path(
        'api/articles/',
        views.api_articles,
        name='api_articles'
    ),

    path(
        'api/articles/<int:article_id>/',
        views.api_article_detail,
        name='api_article_detail'
    ),

    path(
        'api/approved/',
        views.api_approved_article,
        name='api_approved_article'
    ),

    # Newsletter API
    path(
        'api/newsletters/',
        views.api_newsletters,
        name='api_newsletters'
    ),

    path(
        'api/newsletters/<int:newsletter_id>/',
        views.api_newsletter_detail,
        name='api_newsletter_detail'
    ),

    path(
        'api/newsletters/<int:newsletter_id>/approve/',
        views.api_approve_newsletter,
        name='api_approve_newsletter'
    ),

    path(
        'api/publishers/',
        views.api_publishers,
        name='api_publishers'
    ),

    path(
        'api/users/',
        views.api_users,
        name='api_users'
    ),
]
