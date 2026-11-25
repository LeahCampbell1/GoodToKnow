
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


class CustomUser(AbstractUser):
    """Represent a user account with role-based access control.

    Extends Django's ``AbstractUser`` model to support three
    application roles: readers, editors and journalists.

    Each role has different permissions and relationships with
    publishers and other users.

    Readers can subscribe to publishers and journalists.
    Journalists can belong to publishers and create publications.
    Editors can be assigned to publishers and manage their content.

    Role-based permissions are automatically assigned through
    Django groups whenever a user account is saved.

    """

    class Role(models.TextChoices):
        """Define the available application user roles."""

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
        """Save the user and synchronise role-based permissions.

        Performs the save operation within an atomic database
        transaction.

        Before saving, the user account undergoes full model
        validation. The appropriate Django group is then retrieved
        or created according to the user's assigned role.

        Any other application role groups are removed before the
        appropriate group is assigned.

        Finally, the permissions associated with the user's role
        are synchronised with the assigned group.

        :param args: Additional positional arguments passed to
            the parent model save method.
        :param kwargs: Additional keyword arguments passed to
            the parent model save method.
        :returns: None.
        :rtype: None
        """

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
        """Validate user role and associated relationships.

        Ensures that users only maintain publisher relationships
        and subscription relationships appropriate to their role.

        The validation rules prevent:

        * Readers from belonging to journalist or editor publishers.
        * Journalists from belonging to editor publishers or
          maintaining reader subscription relationships.
        * Editors from belonging to journalist publishers or
          maintaining reader subscription relationships.

        :raises ValidationError: If the user has relationships
            that are incompatible with their assigned role.
        :returns: None.
        :rtype: None
        """

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
        """Assign application permissions according to the user role.

        Defines the Django model permissions available to readers,
        journalists and editors.

        Permissions are retrieved using their associated content
        types and permission codenames.

        The resulting permissions are assigned to the supplied
        Django group, replacing its existing permission assignments.

        Reader permissions provide access to view publications.

        Journalist permissions additionally allow article creation,
        editing and deletion, together with newsletter creation
        and editing.

        Editor permissions provide publication management
        capabilities, including publisher management.

        :param group: The Django authentication group receiving
            the role-specific permissions.
        :type group: Group
        :returns: None.
        :rtype: None
        """

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
# ===============
class Publisher(models.Model):
    """Represent a news publisher collaborating with the application.

    Publishers organise journalists and their publications.

    A publisher can be associated with multiple editors and
    journalists. Readers can also subscribe to publishers to
    receive their approved publications.

    """

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return the publisher's name.

        :returns: The name of the publisher.
        :rtype: str
        """
        return self.name


# Article model
# =============
class Article(models.Model):
    """Represent a news article submitted by a journalist.

    Articles contain written content and may optionally include
    an uploaded image.

    Each article has a journalist author and can optionally
    be associated with a publisher.

    Publisher-affiliated articles require editorial approval.
    Independent articles can be approved without publisher
    affiliation.

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
        """Validate article authorship and publisher affiliation.

        Ensures that an article's author has the journalist role.

        If the article is associated with a publisher, the journalist
        must also belong to that publisher.

        :raises ValidationError: If the author is not a journalist
            or does not belong to the associated publisher.
        :returns: None.
        :rtype: None
        """

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
        """Validate and save the article.

        Performs full model validation before saving the article
        to the database.

        :param args: Additional positional arguments passed to
            the parent model save method.
        :param kwargs: Additional keyword arguments passed to
            the parent model save method.
        :returns: None.
        :rtype: None
        """

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        """Return the article title.

        :returns: The title of the article.
        :rtype: str
        """
        return self.title


# Newsletter
# ==========
class Newsletter(models.Model):
    """Represent a curated collection of news articles.

    Newsletters allow journalists to group multiple articles
    into a single publication.

    Each newsletter has a title, description, creation date
    and journalist or editor author.

    Newsletters can optionally be associated with a publisher
    and contain multiple articles through a many-to-many
    relationship.

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
        """Validate the role of the newsletter author.

        Ensures that only users with the journalist or editor
        role can create newsletters.

        :raises ValidationError: If the author does not have
            the journalist or editor role.
        :returns: None.
        :rtype: None
        """

        super().clean()

        if self.author_id and self.author.role not in [
            CustomUser.Role.JOURNALIST,
            CustomUser.Role.EDITOR
        ]:
            raise ValidationError(
                "Only journalists and editors can create newsletters."
            )

    def save(self, *args, **kwargs):
        """Validate and save the newsletter.

        Performs full model validation before saving the newsletter
        to the database.

        :param args: Additional positional arguments passed to
            the parent model save method.
        :param kwargs: Additional keyword arguments passed to
            the parent model save method.
        :returns: None.
        :rtype: None
        """

        self.full_clean()

        super().save(*args, **kwargs)
