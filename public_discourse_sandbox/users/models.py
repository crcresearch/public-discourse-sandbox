from typing import ClassVar

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField

# BaseModel imports
from django.db.models import Model
from django.db.models import DateTimeField
from django.db.models import UUIDField
import uuid
# End of BaseModel imports

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


# Create your models here.
class BaseModel(Model):
    """
    Base model that should be used for all other records in this app.
    Creates a UUID as the main ID to avoid sequential ID generation.
    Also adds a created date and last modified meta fields.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_date = DateTimeField(auto_now_add=True)
    last_modified = DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class User(AbstractUser, BaseModel):
    """
    Default custom user model for Public Discourse Sandbox.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    is_researcher = BooleanField(
        _("is researcher"),
        default=False,
        help_text=_("Designates whether this user is a researcher."),
    )
    last_accessed = models.ForeignKey(
        "pds_app.Experiment", on_delete=models.SET_NULL, null=True
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})
