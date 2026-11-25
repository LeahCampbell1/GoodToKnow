from .models import Publisher, Article, Newsletter

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from rest_framework import status
from unittest.mock import patch, MagicMock


User = get_user_model()


class APITestBase(TestCase):
    """
    Common test setup for the Good To Know REST API.

    Creates readers, journalists, editors and publishers.
    Provides authenticated API clients using token authentication.
    """

    def setUp(self):

        # Create publishers.
        self.publisher1 = Publisher.objects.create(
            name="Daily News",
            description="General news publisher"
        )

        self.publisher2 = Publisher.objects.create(
            name="World News",
            description="International news publisher"
        )

        # Create users.
        self.reader1 = User.objects.create_user(
            username="reader1",
            password="password123",
            email="reader1@test.com",
            role=User.Role.READER
        )

        self.reader2 = User.objects.create_user(
            username="reader2",
            password="password123",
            email="reader2@test.com",
            role=User.Role.READER
        )

        self.journalist1 = User.objects.create_user(
            username="journalist1",
            password="password123",
            email="journalist1@test.com",
            role=User.Role.JOURNALIST
        )

        self.journalist2 = User.objects.create_user(
            username="journalist2",
            password="password123",
            email="journalist2@test.com",
            role=User.Role.JOURNALIST
        )

        self.editor = User.objects.create_user(
            username="editor1",
            password="password123",
            email="editor@test.com",
            role=User.Role.EDITOR
        )

        # Assign journalists to publishers.
        self.journalist1.publishers.add(self.publisher1)
        self.journalist2.publishers.add(self.publisher2)

        # Assign editor to publisher.
        self.editor.editor_publishers.add(self.publisher1)

        # Create reader subscriptions.
        self.reader1.subscribed_publishers.add(self.publisher1)
        self.reader1.subscribed_journalists.add(self.journalist1)

        self.reader2.subscribed_publishers.add(self.publisher2)
        self.reader2.subscribed_journalists.add(self.journalist2)

        # Create articles.
        self.article1 = Article.objects.create(
            title="Daily News Article",
            content="Content from journalist one.",
            author=self.journalist1,
            publisher=self.publisher1,
            approved=True
        )

        self.article2 = Article.objects.create(
            title="World News Article",
            content="Content from journalist two.",
            author=self.journalist2,
            publisher=self.publisher2,
            approved=True
        )

        self.article3 = Article.objects.create(
            title="Pending Article",
            content="Awaiting editor approval.",
            author=self.journalist1,
            publisher=self.publisher1,
            approved=False
        )

        # Create authenticated API clients.
        self.reader_client = self.get_api_client(self.reader1)
        self.reader2_client = self.get_api_client(self.reader2)
        self.journalist_client = self.get_api_client(self.journalist1)
        self.journalist2_client = self.get_api_client(self.journalist2)
        self.editor_client = self.get_api_client(self.editor)

    def get_api_client(self, user):
        """
        Generate an authenticated API client using token authentication.
        """

        token, created = Token.objects.get_or_create(
            user=user
        )

        client = APIClient()

        client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        return client


# Authentication and role based access
class AuthenticationTests(APITestBase):
    """
    Test token authentication and role-based API access.
    """

    def test_reader_can_access_articles(self):

        response = self.reader_client.get(
            reverse("api_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_journalist_can_access_articles(self):

        response = self.journalist_client.get(
            reverse("api_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_editor_can_access_articles(self):

        response = self.editor_client.get(
            reverse("api_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_unauthenticated_user_cannot_access_articles(self):

        client = APIClient()

        response = client.get(
            reverse("api_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_reader_cannot_create_article(self):

        response = self.reader_client.post(
            reverse("api_articles"),
            {
                "title": "Unauthorised Article",
                "content": "Reader attempting to publish."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_editor_cannot_create_article(self):

        response = self.editor_client.post(
            reverse("api_articles"),
            {
                "title": "Editor Article",
                "content": "Editors cannot create articles."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )


# Reader subscription tests
class ReaderSubscriptionTests(APITestBase):
    """
    Verify that readers only retrieve approved articles
    from their subscribed publishers and journalists.
    """

    def test_reader_receives_subscribed_articles(self):

        response = self.reader_client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        article_ids = [
            article["id"]
            for article in response.data
        ]

        self.assertIn(
            self.article1.id,
            article_ids
        )

        self.assertNotIn(
            self.article2.id,
            article_ids
        )

    def test_reader_cannot_retrieve_unsubscribed_articles(self):

        response = self.reader_client.get(
            reverse("api_subscribed_articles")
        )

        article_ids = [
            article["id"]
            for article in response.data
        ]

        self.assertNotIn(
            self.article2.id,
            article_ids
        )

    def test_reader_cannot_retrieve_unapproved_articles(self):

        response = self.reader_client.get(
            reverse("api_subscribed_articles")
        )

        article_ids = [
            article["id"]
            for article in response.data
        ]

        self.assertNotIn(
            self.article3.id,
            article_ids
        )

    def test_second_reader_receives_different_subscriptions(self):

        response = self.reader2_client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        article_ids = [
            article["id"]
            for article in response.data
        ]

        self.assertIn(
            self.article2.id,
            article_ids
        )

        self.assertNotIn(
            self.article1.id,
            article_ids
        )

    def test_reader_can_browse_all_approved_articles(self):

        response = self.reader_client.get(
            reverse("api_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        article_ids = [
            article["id"]
            for article in response.data
        ]

        # General article browsing is not subscription restricted.
        self.assertIn(
            self.article1.id,
            article_ids
        )

        self.assertIn(
            self.article2.id,
            article_ids
        )

        self.assertNotIn(
            self.article3.id,
            article_ids
        )

    def test_journalist_cannot_access_reader_subscriptions_endpoint(self):

        response = self.journalist_client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_editor_cannot_access_reader_subscriptions_endpoint(self):

        response = self.editor_client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )


# Journalist article tests
class JournalistArticleTests(APITestBase):
    """
    Test journalist article creation, validation and ownership.

    Journalists can create articles belonging to publishers
    they are affiliated with. Publisher articles require
    editor approval. Independent articles are automatically
    approved.
    """

    def test_journalist_can_create_publisher_article(self):

        response = self.journalist_client.post(
            reverse("api_articles"),
            {
                "title": "New Daily News Article",
                "content": "An article submitted for approval.",
                "publisher": self.publisher1.id
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        article = Article.objects.get(
            title="New Daily News Article"
        )

        self.assertEqual(
            article.author,
            self.journalist1
        )

        self.assertEqual(
            article.publisher,
            self.publisher1
        )

        self.assertFalse(article.approved)

    def test_journalist_can_create_independent_article(self):

        response = self.journalist_client.post(
            reverse("api_articles"),
            {
                "title": "Independent News Article",
                "content": "An independently published article."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        article = Article.objects.get(
            title="Independent News Article"
        )

        self.assertEqual(
            article.author,
            self.journalist1
        )

        self.assertIsNone(
            article.publisher
        )

        self.assertTrue(article.approved)

    def test_journalist_cannot_use_unassigned_publisher(self):

        response = self.journalist_client.post(
            reverse("api_articles"),
            {
                "title": "Unauthorised Publisher Article",
                "content": "This publisher is not assigned.",
                "publisher": self.publisher2.id
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertFalse(
            Article.objects.filter(
                title="Unauthorised Publisher Article"
            ).exists()
        )

    def test_reader_cannot_create_article(self):

        response = self.reader_client.post(
            reverse("api_articles"),
            {
                "title": "Reader Article",
                "content": "Readers cannot create articles."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_journalist_cannot_create_article_with_invalid_data(self):

        response = self.journalist_client.post(
            reverse("api_articles"),
            {
                "title": "",
                "content": ""
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_journalist_cannot_set_approved_status(self):

        response = self.journalist_client.post(
            reverse("api_articles"),
            {
                "title": "Attempted Self Approval",
                "content": "Testing approval restrictions.",
                "publisher": self.publisher1.id,
                "approved": True
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        article = Article.objects.get(
            title="Attempted Self Approval"
        )

        # The API must ignore the submitted approval value.
        self.assertFalse(article.approved)

    def test_journalist_cannot_create_article_for_another_journalist(self):

        response = self.journalist_client.post(
            reverse("api_articles"),
            {
                "title": "Incorrect Author",
                "content": "Testing author ownership.",
                "author": self.journalist2.id,
                "publisher": self.publisher1.id
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        article = Article.objects.get(
            title="Incorrect Author"
        )

        # The authenticated journalist must remain the author.
        self.assertEqual(
            article.author,
            self.journalist1
        )


# Editor article tests
class EditorArticleTests(APITestBase):
    """
    Test editor permissions for approving, editing and deleting
    articles belonging to their assigned publishers.
    """

    def test_editor_can_approve_article(self):

        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_302_FOUND
        )

        self.article3.refresh_from_db()

        self.assertTrue(
            self.article3.approved
        )

    def test_editor_can_delete_own_publisher_article(self):

        article_id = self.article1.id

        response = self.editor_client.delete(
            reverse("api_article_detail", args=[article_id])
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertFalse(
            Article.objects.filter(id=article_id).exists()
        )

    def test_editor_cannot_delete_other_publishers_article(self):

        article_id = self.article2.id

        response = self.editor_client.delete(
            reverse("api_article_detail", args=[article_id])
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertTrue(
            Article.objects.filter(id=article_id).exists()
        )

    def test_editor_can_edit_own_publisher_article(self):

        response = self.editor_client.put(
            reverse(
                "api_article_detail",
                args=[self.article1.id]
            ),
            {
                "title": "Edited Daily News Article",
                "content": "Updated by the editor.",
                "author": self.journalist1.id,
                "publisher": self.publisher1.id
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.article1.refresh_from_db()

        self.assertEqual(
            self.article1.title,
            "Edited Daily News Article"
        )

        # Editor changes require fresh approval.
        self.assertFalse(self.article1.approved)

    def test_editor_cannot_edit_other_publishers_article(self):

        response = self.editor_client.put(
            reverse(
                "api_article_detail",
                args=[self.article2.id]
            ),
            {
                "title": "Unauthorised Edit",
                "content": "This edit should fail.",
                "author": self.journalist2.id
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.article2.refresh_from_db()

        self.assertEqual(
            self.article2.title,
            "World News Article"
        )

    def test_editor_cannot_change_article_author(self):

        original_author = self.article1.author

        response = self.editor_client.put(
            reverse(
                "api_article_detail",
                args=[self.article1.id]
            ),
            {
                "title": "Attempted Author Change",
                "content": "Testing author ownership restrictions.",
                "author": self.journalist2.id
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.article1.refresh_from_db()

        # The original author must remain unchanged.
        self.assertEqual(
            self.article1.author,
            original_author
        )

        self.assertNotEqual(
            self.article1.author,
            self.journalist2
        )

        # Other permitted changes should still be saved.
        self.assertEqual(
            self.article1.title,
            "Attempted Author Change"
        )

    def test_editor_cannot_delete_article_without_authentication(self):

        client = APIClient()

        response = client.delete(
            reverse(
                "api_article_detail",
                args=[self.article1.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )


# Newsletter API tests
class NewsletterTests(APITestBase):
    """
    Test newsletter retrieval and editor approval.

    Newsletters are created internally, not through the API.

    Authenticated users can retrieve approved newsletters.
    Pending newsletters are only accessible to authorised editors.
    Editors can approve newsletters belonging to their publishers.
    """

    def setUp(self):
        super().setUp()

        self.newsletter1 = Newsletter.objects.create(
            title="Daily News Newsletter",
            description="Latest Daily News articles.",
            author=self.journalist1,
            publisher=self.publisher1,
            approved=True
        )

        self.newsletter1.articles.add(
            self.article1
        )

        self.newsletter2 = Newsletter.objects.create(
            title="World News Newsletter",
            description="Latest international news.",
            author=self.journalist2,
            publisher=self.publisher2,
            approved=True
        )

        self.newsletter2.articles.add(
            self.article2
        )

        self.newsletter3 = Newsletter.objects.create(
            title="Pending Newsletter",
            description="Awaiting editor approval.",
            author=self.journalist1,
            publisher=self.publisher1,
            approved=False
        )

    # Newsletter listing
    def test_authenticated_reader_can_retrieve_newsletters(self):

        response = self.reader_client.get(
            reverse("api_newsletters")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data),
            2
        )

    def test_authenticated_journalist_can_retrieve_newsletters(self):

        response = self.journalist_client.get(
            reverse("api_newsletters")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_authenticated_editor_can_retrieve_newsletters(self):

        response = self.editor_client.get(
            reverse("api_newsletters")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_unauthenticated_user_cannot_retrieve_newsletters(self):

        response = APIClient().get(
            reverse("api_newsletters")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_unapproved_newsletters_are_excluded_from_listing(self):

        response = self.reader_client.get(
            reverse("api_newsletters")
        )

        newsletter_ids = [
            newsletter["id"]
            for newsletter in response.data
        ]

        self.assertIn(
            self.newsletter1.id,
            newsletter_ids
        )

        self.assertIn(
            self.newsletter2.id,
            newsletter_ids
        )

        self.assertNotIn(
            self.newsletter3.id,
            newsletter_ids
        )

    # Individual newsletter retrieval
    def test_reader_can_retrieve_approved_newsletter(self):

        response = self.reader_client.get(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter1.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["title"],
            self.newsletter1.title
        )

    def test_reader_cannot_retrieve_unapproved_newsletter(self):

        response = self.reader_client.get(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_editor_can_retrieve_pending_newsletter_from_own_publisher(self):

        response = self.editor_client.get(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_editor_cannot_retrieve_other_publishers_pending_newsletter(self):

        # Create an editor assigned to publisher2.
        other_editor = User.objects.create_user(
            username="editor2",
            password="password123",
            email="editor2@test.com",
            role=User.Role.EDITOR
        )

        other_editor.editor_publishers.add(
            self.publisher2
        )

        other_editor_client = self.get_api_client(
            other_editor
        )

        response = other_editor_client.get(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_nonexistent_newsletter_returns_404(self):

        response = self.reader_client.get(
            reverse(
                "api_newsletter_detail",
                args=[99999]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    # Newsletter modification restrictions
    def test_journalist_cannot_create_newsletter(self):

        response = self.journalist_client.post(
            reverse("api_newsletters"),
            {
                "title": "Unauthorised Newsletter",
                "description": "Journalists cannot create newsletters."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_reader_cannot_create_newsletter(self):

        response = self.reader_client.post(
            reverse("api_newsletters"),
            {
                "title": "Reader Newsletter",
                "description": "Readers cannot create newsletters."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_journalist_cannot_edit_newsletter(self):

        response = self.journalist_client.put(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter1.id]
            ),
            {
                "title": "Modified Newsletter",
                "description": "Attempted modification."
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_reader_cannot_delete_newsletter(self):

        response = self.reader_client.delete(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter1.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

        self.assertTrue(
            Newsletter.objects.filter(
                id=self.newsletter1.id
            ).exists()
        )

    # Newsletter approval
    def test_editor_can_approve_newsletter(self):

        response = self.editor_client.post(
            reverse(
                "api_approve_newsletter",
                args=[self.newsletter3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.newsletter3.refresh_from_db()

        self.assertTrue(
            self.newsletter3.approved
        )

    def test_editor_cannot_approve_other_publishers_newsletter(self):

        response = self.editor_client.post(
            reverse(
                "api_approve_newsletter",
                args=[self.newsletter2.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

        self.newsletter2.refresh_from_db()

        self.assertTrue(
            self.newsletter2.approved
        )

    def test_reader_cannot_approve_newsletter(self):

        response = self.reader_client.post(
            reverse(
                "api_approve_newsletter",
                args=[self.newsletter3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_journalist_cannot_approve_newsletter(self):

        response = self.journalist_client.post(
            reverse(
                "api_approve_newsletter",
                args=[self.newsletter3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    # Newsletter article associations
    def test_newsletter_articles_are_associated_correctly(self):

        self.assertIn(
            self.article1,
            self.newsletter1.articles.all()
        )

        self.assertNotIn(
            self.article2,
            self.newsletter1.articles.all()
        )

    def test_newsletter_response_contains_associated_articles(self):

        response = self.reader_client.get(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter1.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        article_ids = [
            article["id"]
            for article in response.data["articles"]
        ]

        self.assertIn(
            self.article1.id,
            article_ids
        )

    def test_newsletter_response_contains_publisher(self):

        response = self.reader_client.get(
            reverse(
                "api_newsletter_detail",
                args=[self.newsletter1.id]
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIsNotNone(
            response.data["publisher"]
        )


# Article distribution tests
class ArticleDistributionTests(APITestBase):
    """
    Test article distribution following editor approval.

    Tests:
    - Email distribution to publisher subscribers.
    - Email distribution to journalist subscribers.
    - No email when there are no subscribers.
    - API integration with /api/approved/.
    - Failed API requests.
    """

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_approved_article_is_distributed(
        self,
        mock_email_send,
        mock_api_post
    ):

        mock_email_send.return_value = 1

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        mock_api_post.return_value = mock_response

        # Approve and distribute the article.
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.article3.refresh_from_db()

        self.assertTrue(
            self.article3.approved
        )

        # Verify email delivery was attempted.
        mock_email_send.assert_called_once()

        # Verify the approved article API was called.
        mock_api_post.assert_called_once()

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_distribution_emails_publisher_subscribers(
        self,
        mock_email_send,
        mock_api_post
    ):

        mock_email_send.return_value = 1

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        mock_api_post.return_value = mock_response

        # Subscribe reader to the article publisher.
        self.reader1.subscribed_publishers.add(
            self.publisher1
        )

        self.client.force_login(self.editor)

        self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        mock_email_send.assert_called_once()

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_distribution_emails_journalist_subscribers(
        self,
        mock_email_send,
        mock_api_post
    ):

        mock_email_send.return_value = 1

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        mock_api_post.return_value = mock_response

        # Create a reader subscribed to the journalist.
        self.reader2.subscribed_journalists.add(
            self.journalist1
        )

        self.client.force_login(self.editor)

        self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        mock_email_send.assert_called_once()

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_no_email_sent_without_subscribers(
        self,
        mock_email_send,
        mock_api_post
    ):

        # Remove all subscribers from this publisher and journalist.
        self.reader1.subscribed_publishers.remove(
            self.publisher1
        )

        self.reader1.subscribed_journalists.remove(
            self.journalist1
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        mock_api_post.return_value = mock_response

        self.client.force_login(self.editor)

        self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        mock_email_send.assert_not_called()

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_approved_article_is_posted_to_api(
        self,
        mock_email_send,
        mock_api_post
    ):

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        mock_api_post.return_value = mock_response

        self.client.force_login(self.editor)

        self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        mock_api_post.assert_called_once()

        # Check that the request contains the correct article ID.
        call_kwargs = mock_api_post.call_args.kwargs

        self.assertEqual(
            call_kwargs["json"]["article_id"],
            self.article3.id
        )

        # Verify token authentication is included.
        self.assertIn(
            "Authorization",
            call_kwargs["headers"]
        )

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_api_failure_does_not_undo_article_approval(
        self,
        mock_email_send,
        mock_api_post
    ):

        mock_response = MagicMock()

        mock_response.raise_for_status.side_effect = (
            Exception("API unavailable")
        )

        mock_api_post.return_value = mock_response

        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.article3.refresh_from_db()

        # Approval is saved before distribution is attempted.
        self.assertTrue(
            self.article3.approved
        )

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage.send")
    def test_email_failure_does_not_undo_article_approval(
        self,
        mock_email_send,
        mock_api_post
    ):

        mock_email_send.side_effect = Exception(
            "Email service unavailable"
        )

        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "approve_article",
                args=[self.article3.id]
            )
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.article3.refresh_from_db()

        self.assertTrue(
            self.article3.approved
        )

        # Email failure prevents the subsequent API request.
        mock_api_post.assert_not_called()


# User API tests
class UserAPITests(APITestBase):
    """
    Test that editors can only retrieve readers
    subscribed to their assigned publishers.
    """

    def test_editor_can_retrieve_subscribed_readers(self):

        response = self.editor_client.get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}

        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        user_ids = [
            user["id"]
            for user in response.data
        ]

        self.assertIn(
            self.reader1.id,
            user_ids
        )

        self.assertNotIn(
            self.reader2.id,
            user_ids
        )

    def test_reader_cannot_retrieve_users(self):

        response = self.reader_client.get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_journalist_cannot_retrieve_users(self):

        response = self.journalist_client.get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_unauthenticated_user_cannot_retrieve_users(self):

        response = APIClient().get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_editor_does_not_receive_unsubscribed_readers(self):

        response = self.editor_client.get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}
        )

        user_ids = [
            user["id"]
            for user in response.data
        ]

        self.assertNotIn(
            self.reader2.id,
            user_ids
        )

    def test_editor_receives_new_subscribers(self):

        # Subscribe reader2 to publisher1.
        self.reader2.subscribed_publishers.add(
            self.publisher1
        )

        response = self.editor_client.get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}
        )

        user_ids = [
            user["id"]
            for user in response.data
        ]

        self.assertIn(
            self.reader2.id,
            user_ids
        )

    def test_editor_receives_no_duplicate_users(self):

        # Add another publisher subscription.
        self.reader1.subscribed_publishers.add(
            self.publisher2
        )

        response = self.editor_client.get(
            reverse("api_users"),
            {"publisher_id": self.publisher1.id}
        )

        user_ids = [
            user["id"]
            for user in response.data
        ]

        self.assertEqual(
            user_ids.count(self.reader1.id),
            1
        )


class PublisherAPITests(APITestBase):

    def test_authenticated_user_can_retrieve_publishers(self):

        response = self.reader_client.get(
            reverse("api_publishers")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data),
            2
        )

    def test_unauthenticated_user_cannot_retrieve_publishers(self):

        response = APIClient().get(
            reverse("api_publishers")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
