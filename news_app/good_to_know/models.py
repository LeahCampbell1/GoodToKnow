from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


class CustomUser(AbstractUser):

    class Role(models.TextChoices):
        READER = "READER", "Reader"
        EDITOR = "EDITOR", "Editor"
        JOURNALIST = "JOURNALIST", "Journalist"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READER
    )

    publishers = models.ManyToManyField(
        "Publisher",
        related_name="journalists",
        blank=True
    )

    editor_publishers = models.ManyToManyField(
        "Publisher",
        related_name="editors",
        blank=True
    )

    subscribed_publishers = models.ManyToManyField(
        "Publisher",
        related_name="subscribers",
        blank=True
    )

    subscribed_journalists = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="journalist_subscribers",
        limit_choices_to={"role": "JOURNALIST"},
        blank=True
    )

    def save(self, *args, **kwargs):

        with transaction.atomic():

            self.full_clean()
            super().save(*args, **kwargs)

            # Assign the appropriate group.
            group_name = self.get_role_display()

            group, created = Group.objects.get_or_create(
                name=group_name
            )

            # Remove other role groups.
            role_groups = Group.objects.filter(
                name__in=["Reader", "Editor", "Journalist"]
            )

            self.groups.remove(*role_groups)
            self.groups.add(group)

            # Assign group permissions.
            self.assign_group_permissions(group)

    def clean(self):

        super().clean()

        if not self.pk:
            return

        if self.role == self.Role.READER:

            if self.publishers.exists() or self.editor_publishers.exists():
                raise ValidationError(
                    "Readers cannot belong to journalist or editor publishers."
                )

        elif self.role == self.Role.JOURNALIST:

            if self.editor_publishers.exists():
                raise ValidationError(
                    "Journalists cannot belong to editor publishers."
                )

            if self.subscribed_publishers.exists() or self.subscribed_journalists.exists():
                raise ValidationError(
                    "Journalists cannot have reader subscription fields."
                )

        elif self.role == self.Role.EDITOR:

            if self.publishers.exists():
                raise ValidationError(
                    "Editors cannot belong to journalist publishers."
                )

            if self.subscribed_publishers.exists() or self.subscribed_journalists.exists():
                raise ValidationError(
                    "Editors cannot have reader subscription fields."
                )

    def assign_group_permissions(self, group):

        permissions = {
            self.Role.READER: {
                "article": ["view_article"],
                "newsletter": ["view_newsletter"],
                "publisher": ["view_publisher"],
            },

            self.Role.JOURNALIST: {
                "article": [
                    "view_article",
                    "add_article",
                    "change_article",
                    "delete_article",
                ],
                "newsletter": [
                    "view_newsletter",
                    "add_newsletter",
                    "change_newsletter",
                ],
                "publisher": ["view_publisher"],
            },

            self.Role.EDITOR: {
                "article": [
                    "view_article",
                    "add_article",
                    "change_article",
                    "delete_article",
                ],
                "newsletter": [
                    "view_newsletter",
                    "add_newsletter",
                    "change_newsletter",
                    "delete_newsletter",
                ],
                "publisher": [
                    "view_publisher",
                    "add_publisher",
                    "change_publisher",
                    "delete_publisher",
                ],
            },
        }

        role_permissions = permissions[self.role]

        assigned_permissions = []

        for model_name, codenames in role_permissions.items():

            content_type = ContentType.objects.get(
                app_label=self._meta.app_label,
                model=model_name
            )

            model_permissions = Permission.objects.filter(
                content_type=content_type,
                codename__in=codenames
            )

            assigned_permissions.extend(model_permissions)

        group.permissions.set(assigned_permissions)


# Publisher model
class Publisher(models.Model):
    """
    Represents a news publisher.

    Satisfies specification:
    - A publisher can have multiple editors.
    - A publisher can have multiple journalists.
    """

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# Article model
class Article(models.Model):
    """
    Represents a news article.

    Satisfies specification:
    - Articles have a title, content, author, created_at,
      approved status and publisher.
    - Articles have a journalist author.
    - Articles can optionally belong to a publisher.
    """

    title = models.CharField(max_length=255)

    content = models.TextField()

    # Allows an image to be uploaded with an article.
    image = models.ImageField(
        upload_to="articles/",
        blank=True,
        null=True
    )

    # Every article has a journalist author.
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="articles"
    )

    # Optional publisher association.
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Editors can approve articles.
    approved = models.BooleanField(default=False)

    def clean(self):

        super().clean()

        if self.author and self.author.role != CustomUser.Role.JOURNALIST:
            raise ValidationError(
                "Only journalists can author articles."
            )

        if self.author and self.publisher:

            if not self.author.publishers.filter(
                pk=self.publisher_id
            ).exists():

                raise ValidationError(
                    "The journalist must belong to the article's publisher."
                )

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# Newsletter
class Newsletter(models.Model):
    """
    Represents a curated collection of articles.

    Satisfies specification:
    - Newsletters have a title, description, created_at
      and journalist author.
    - Newsletters can contain multiple articles.
    """

    title = models.CharField(max_length=255)

    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="newsletters",
    )

    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='newsletters'
    )

    articles = models.ManyToManyField(
        Article,
        related_name="newsletters",
        blank=True
    )
    approved = models.BooleanField(default=False)

    def clean(self):
        super().clean()

        if self.author_id and self.author.role not in [
            CustomUser.Role.JOURNALIST,
            CustomUser.Role.EDITOR
        ]:
            raise ValidationError(
                "Only journalists and editors can create newsletters."
            )

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)
