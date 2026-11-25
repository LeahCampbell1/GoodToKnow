from django.test import TestCase, Client, RequestFactory
from django.urls import reverse

from rest_framework.test import APITestCase
from rest_framework import status

from good_to_know.models import (
    CustomUser,
    Publisher,
    Article,
    Newsletter
)
from good_to_know.views import distribute_approved_article

from unittest.mock import patch, MagicMock


class BaseAPITestCase(APITestCase):

    def setUp(self):

        # Publishers
        self.publisher1 = Publisher.objects.create(
            name="Publisher One"
        )

        self.publisher2 = Publisher.objects.create(
            name="Publisher Two"
        )

        # Reader
        self.reader = CustomUser.objects.create_user(
            username="reader",
            password="password123",
            role=CustomUser.Role.READER
        )

        # Journalists
        self.journalist = CustomUser.objects.create_user(
            username="journalist",
            password="password123",
            role=CustomUser.Role.JOURNALIST
        )

        self.journalist2 = CustomUser.objects.create_user(
            username="journalist2",
            password="password123",
            role=CustomUser.Role.JOURNALIST
        )

        # Editor
        self.editor = CustomUser.objects.create_user(
            username="editor",
            password="password123",
            role=CustomUser.Role.EDITOR
        )

        # Assign publishers
        self.journalist.publishers.add(self.publisher1)
        self.journalist2.publishers.add(self.publisher2)

        self.editor.editor_publishers.add(self.publisher1)

        # Articles
        self.article1 = Article.objects.create(
            title="Article One",
            content="Content One",
            author=self.journalist,
            publisher=self.publisher1,
            approved=True
        )

        self.article2 = Article.objects.create(
            title="Article Two",
            content="Content Two",
            author=self.journalist2,
            publisher=self.publisher2,
            approved=True
        )

        self.pending_article = Article.objects.create(
            title="Pending Article",
            content="Waiting for approval",
            author=self.journalist,
            publisher=self.publisher1,
            approved=False
        )

        # Subscriptions
        self.reader.subscribed_publishers.add(
            self.publisher1
        )

        self.reader.subscribed_journalists.add(
            self.journalist
        )


#  Authenticated access per role
class AuthenticationTests(BaseAPITestCase):

    def test_unauthenticated_user_denied(self):

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_reader_can_access_subscribed_articles(self):

        self.client.force_authenticate(
            user=self.reader
        )

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_journalist_cannot_access_reader_endpoint(self):

        self.client.force_authenticate(
            user=self.journalist
        )

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_editor_cannot_access_reader_endpoint(self):

        self.client.force_authenticate(
            user=self.editor
        )

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_unauthenticated_user_cannot_create_article(self):
        response = self.client.post(
            reverse("api_articles"),
            {
                "title": "Unauthorised Article",
                "content": "Content"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )


    def test_reader_cannot_approve_article(self):
        self.client.force_authenticate(user=self.reader)

        response = self.client.post(
            reverse(
                "approve_article",
                args=[self.pending_article.id]
            )
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )


# Reader subscription tests
class ReaderSubscriptionTests(BaseAPITestCase):

    def test_reader_only_receives_subscribed_articles(self):

        self.client.force_authenticate(
            user=self.reader
        )

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(response.status_code, 200)

        article_ids = [
            article["id"]
            for article in response.data
        ]

        self.assertIn(self.article1.id, article_ids)

        self.assertNotIn(self.article2.id, article_ids)

        self.assertNotIn(
            self.pending_article.id,
            article_ids
        )

    def test_reader_cannot_receive_unsubscribed_content(self):

        self.reader.subscribed_publishers.clear()
        self.reader.subscribed_journalists.clear()

        self.client.force_authenticate(
            user=self.reader
        )

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_reader_receives_journalist_subscription_content(self):

        self.reader.subscribed_publishers.clear()

        self.client.force_authenticate(
            user=self.reader
        )

        response = self.client.get(
            reverse("api_subscribed_articles")
        )

        article_ids = [
            article["id"]
            for article in response.data
        ]

        self.assertIn(self.article1.id, article_ids)


# 3. Journalist article creation
class JournalistArticleTests(BaseAPITestCase):

    def test_journalist_can_create_article(self):

        self.client.force_authenticate(
            user=self.journalist
        )

        data = {
            "title": "New Article",
            "content": "New article content",
            "publisher": self.publisher1.id
        }

        response = self.client.post(
            reverse("api_articles"),
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        article = Article.objects.get(
            title="New Article"
        )

        self.assertEqual(article.author, self.journalist)
        self.assertFalse(article.approved)

    def test_journalist_can_create_independent_article(self):

        self.client.force_authenticate(
            user=self.journalist
        )

        response = self.client.post(
            reverse("api_articles"),
            {
                "title": "Independent Article",
                "content": "Independent content"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        article = Article.objects.get(
            title="Independent Article"
        )

        self.assertTrue(article.approved)

    def test_reader_cannot_create_article(self):

        self.client.force_authenticate(
            user=self.reader
        )

        response = self.client.post(
            reverse("api_articles"),
            {
                "title": "Reader Article",
                "content": "Not allowed"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_journalist_cannot_use_wrong_publisher(self):

        self.client.force_authenticate(
            user=self.journalist
        )

        response = self.client.post(
            reverse("api_articles"),
            {
                "title": "Wrong Publisher",
                "content": "Invalid publisher",
                "publisher": self.publisher2.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 403)


# ==========================================
# 4. EDITOR APPROVAL AND DELETION
# ==========================================

class EditorTests(BaseAPITestCase):

    def test_editor_can_delete_article(self):

        self.client.force_authenticate(
            user=self.editor
        )

        response = self.client.delete(
            reverse(
                "api_article_detail",
                args=[self.article1.id]
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            Article.objects.filter(
                id=self.article1.id
            ).exists()
        )

    def test_editor_cannot_delete_other_publishers_article(self):

        self.client.force_authenticate(
            user=self.editor
        )

        response = self.client.delete(
            reverse(
                "api_article_detail",
                args=[self.article2.id]
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_editor_can_approve_article(self):

        from django.test import Client
        from unittest.mock import patch

        client = Client()
        client.force_login(self.editor)

        with patch(
            "good_to_know.views.distribute_approved_article"
        ) as mock_distribution:

            response = client.post(
                reverse(
                    "approve_article",
                    args=[self.pending_article.id]
                )
            )

        self.assertEqual(response.status_code, 302)

        self.pending_article.refresh_from_db()

        self.assertTrue(self.pending_article.approved)

        mock_distribution.assert_called_once()

    def test_editor_cannot_approve_other_publishers_article(self):

        from django.test import Client

        client = Client()
        client.force_login(self.editor)

        response = client.post(
            reverse(
                "approve_article",
                args=[self.article2.id]
            )
        )

        self.assertEqual(response.status_code, 404)


class NewsletterTests(TestCase):

    def setUp(self):

        self.publisher = Publisher.objects.create(
            name="Test Publisher"
        )

        self.journalist = CustomUser.objects.create_user(
            username="journalist",
            password="password123",
            role=CustomUser.Role.JOURNALIST
        )

        self.editor = CustomUser.objects.create_user(
            username="editor",
            password="password123",
            role=CustomUser.Role.EDITOR
        )

        self.reader = CustomUser.objects.create_user(
            username="reader",
            password="password123",
            role=CustomUser.Role.READER
        )

        self.journalist.publishers.add(self.publisher)
        self.editor.editor_publishers.add(self.publisher)

        self.article = Article.objects.create(
            title="Newsletter Article",
            content="Article content",
            author=self.journalist,
            publisher=self.publisher,
            approved=True
        )

        self.newsletter = Newsletter.objects.create(
            title="Weekly Newsletter",
            description="Weekly news",
            author=self.journalist,
            publisher=self.publisher,
            approved=False
        )

        self.newsletter.articles.add(self.article)

        self.client = Client()

    def test_newsletter_contains_articles(self):

        self.assertEqual(
            self.newsletter.articles.count(),
            1
        )

    def test_editor_can_approve_newsletter(self):

        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "approve_newsletter",
                args=[self.newsletter.id]
            )
        )

        self.assertEqual(response.status_code, 302)

        self.newsletter.refresh_from_db()

        self.assertTrue(self.newsletter.approved)

    def test_reader_cannot_view_pending_newsletter(self):

        self.client.force_login(self.reader)

        response = self.client.get(
            reverse(
                "newsletter_detail",
                args=[self.newsletter.id]
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_reader_can_view_approved_newsletter(self):

        self.newsletter.approved = True
        self.newsletter.save()

        self.client.force_login(self.reader)

        response = self.client.get(
            reverse(
                "newsletter_detail",
                args=[self.newsletter.id]
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_editor_can_delete_newsletter(self):

        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "editor_delete_newsletter",
                args=[self.newsletter.id]
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            Newsletter.objects.filter(
                id=self.newsletter.id
            ).exists()
        )


class DistributionTests(TestCase):

    def setUp(self):

        self.publisher = Publisher.objects.create(
            name="Test Publisher"
        )

        self.journalist = CustomUser.objects.create_user(
            username="journalist",
            password="password123",
            email="journalist@test.com",
            role=CustomUser.Role.JOURNALIST
        )

        self.reader = CustomUser.objects.create_user(
            username="reader",
            password="password123",
            email="reader@test.com",
            role=CustomUser.Role.READER
        )

        self.editor = CustomUser.objects.create_user(
            username="editor",
            password="password123",
            role=CustomUser.Role.EDITOR
        )

        self.journalist.publishers.add(self.publisher)
        self.editor.editor_publishers.add(self.publisher)

        self.reader.subscribed_publishers.add(self.publisher)

        self.article = Article.objects.create(
            title="Approved Article",
            content="Article content",
            author=self.journalist,
            publisher=self.publisher,
            approved=True
        )

        self.factory = RequestFactory()

        self.request = self.factory.post("/editor/dashboard/")
        self.request.user = self.editor

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage")
    def test_article_is_distributed_successfully(
        self,
        mock_email,
        mock_post
    ):

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        distribute_approved_article(
            self.article,
            self.request
        )

        # Email is created and sent.
        mock_email.assert_called_once()
        mock_email.return_value.send.assert_called_once()

        # API request is made.
        mock_post.assert_called_once()

        self.assertEqual(
            mock_post.call_args.kwargs["json"]["article_id"],
            self.article.id
        )

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage")
    def test_unapproved_article_is_not_distributed(
        self,
        mock_email,
        mock_post
    ):

        self.article.approved = False

        distribute_approved_article(
            self.article,
            self.request
        )

        mock_email.assert_not_called()
        mock_post.assert_not_called()

    @patch("good_to_know.views.requests.post")
    @patch("good_to_know.views.EmailMessage")
    def test_api_failure_is_raised(
        self,
        mock_email,
        mock_post
    ):

        mock_response = MagicMock()

        mock_response.raise_for_status.side_effect = (
            Exception("API connection failed")
        )

        mock_post.return_value = mock_response

        with self.assertRaises(Exception):

            distribute_approved_article(
                self.article,
                self.request
            )

        mock_post.assert_called_once()
