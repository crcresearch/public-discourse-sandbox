import hashlib
import secrets
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django_notification_system.models import NotificationTarget
from django_notification_system.models import TargetUserRecord

from .utils import check_profanity

User = get_user_model()


# Create your models here.
class BaseModel(models.Model):
    """
    Base model that should be used for all other records in this app.
    Creates a UUID as the main ID to avoid sequential ID generation.
    Also adds a created date and last modified meta fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class UndeletedExperimentManager(models.Manager):
    """
    Custom manager for Experiment model that only returns non-deleted experiments.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Experiment(BaseModel):
    """
    Experiment model.
    """

    name = models.CharField(max_length=255)
    identifier = models.CharField(max_length=5, unique=True)
    description = models.TextField()
    irb_additions = models.TextField(null=True, blank=True)
    options = models.JSONField(default=dict)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
    )  # This defines what user "owns" this experiment
    is_deleted = models.BooleanField(default=False)

    # Add custom managers
    all_objects = models.Manager()  # Default manager that shows all experiments
    objects = (
        UndeletedExperimentManager()
    )  # Custom manager that only shows non-deleted experiments

    def __str__(self):
        return f"{self.name}"

    def create_identifier(self):
        """
        Create a unique identifier for the experiment.
        """
        tries = 0
        # Create a hash digest of the experiment UUID concatenated with tries
        identifier = hashlib.sha256(f"{self.id}{tries}".encode()).hexdigest()[:5]
        # Check if the identifier is already in use
        if Experiment.objects.filter(identifier=identifier).exists():
            tries += 1
            return self.create_identifier()
        return identifier

    def get_option(self, option_key, default=None):
        """
        Get a specific option value from the options JSONField.

        Args:
            option_key: The key to retrieve from the options dictionary
            default: Value to return if the key doesn't exist (default: None)

        Returns:
            The value associated with the option_key, or default if not found
        """
        return self.options.get(option_key, default)

    def set_option(self, option_key, value, save_changes=True):
        """
        Set a specific option value in the options JSONField.

        Args:
            option_key: The key to set in the options dictionary
            value: The value to set for the given key
            save_changes: Whether to save the model after setting the option (default: True)

        Returns:
            The updated value
        """
        if self.options is None:
            self.options = {}

        self.options[option_key] = value

        if save_changes:
            self.save(update_fields=["options", "last_modified"])

        return value

    def save(self, *args, **kwargs):
        if not self.identifier:
            self.identifier = self.create_identifier()
        super().save(*args, **kwargs)


class UserProfile(BaseModel):
    """
    User profile model.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    display_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    banner_picture = models.ImageField(
        upload_to="banner_pictures/", null=True, blank=True,
    )
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", null=True, blank=True,
    )
    dorm_name = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    bio = models.TextField(null=True, blank=True)
    num_followers = models.IntegerField(default=0)
    num_following = models.IntegerField(default=0)
    is_digital_twin = models.BooleanField(default=False)
    is_collaborator = models.BooleanField(
        default=False,
    )  # Works with the experiment owner to administer the experiment
    is_moderator = models.BooleanField(
        default=False,
    )  # Delete posts, ban / report users
    is_banned = models.BooleanField(
        default=False,
    )  # Cannot post, reply, or view content
    is_private = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        unique_together = ("username", "experiment")

    def __str__(self):
        bot_status = " (Digital Twin)" if self.is_digital_twin else ""
        return f"{self.username}{bot_status}"

    def is_experiment_moderator(self):
        """
        Check if this user profile has moderator permissions for the experiment.
        A user is considered a moderator if they:
        1. Own the experiment (are the creator)
        2. Are a collaborator
        3. Have the is_moderator flag set
        """
        return (
            self.experiment.creator == self.user  # User owns the experiment
            or self.is_collaborator  # User is a collaborator
            or self.is_moderator  # User has moderator flag
        )

    def save(self, *args, **kwargs):
        # Update the user's last_accessed experiment
        if not self.is_digital_twin:
            self.user.last_accessed = self.experiment
            self.user.save(update_fields=["last_accessed"])

            # Find and update any pending invitations for this user and experiment
            ExperimentInvitation.objects.filter(
                experiment=self.experiment,
                email=self.user.email,
                is_accepted=False,
                is_deleted=False,
            ).update(is_accepted=True)

            email_target = NotificationTarget.objects.get(name="Email",
                                                          notification_module_name="email")
            TargetUserRecord.objects.update_or_create(
                    user=self.user,
                    target=email_target,
                    target_user_id=self.user.email,
                    defaults={
                        "active": True,
                        "description": "Email notification target",
                    })
            if self.phone_number:
                twiliotarget = NotificationTarget.objects.get(name="Twilio")
                TargetUserRecord.objects.update_or_create(
                        user=self.user,
                        target=twiliotarget,
                        target_user_id=self.phone_number,
                        defaults={
                            "description": f"{self.username}'s twilio",
                            "active": True,
                        }
                    )
        super().save(*args, **kwargs)


class UndeletedPostManager(models.Manager):
    def get_queryset(self):
        # Only return posts that are not deleted or from user profiles that are not banned
        return (
            super()
            .get_queryset()
            .filter(is_deleted=False)
            .exclude(user_profile__is_banned=True)
        )


class Post(BaseModel):
    """
    Post model.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    content = models.TextField()
    parent_post = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
    )
    depth = models.IntegerField(default=0)
    num_upvotes = models.IntegerField(default=0)
    num_downvotes = models.IntegerField(default=0)
    num_comments = models.IntegerField(default=0)
    num_shares = models.IntegerField(default=0)  # any repost or quote of this post
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    repost_source = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reposts",
    )

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        status = " (Deleted)" if self.is_deleted else ""
        return f"Post by {self.user_profile.username}: {preview}{status}"

    all_objects = models.Manager()
    objects = UndeletedPostManager()

    def get_comment_count(self):
        """
        Returns the number of posts that have this post as their parent.
        Also only non-deleted posts because of the custom modelManager
        """
        return Post.objects.filter(parent_post=self).count()

    def parse_hashtags(self):
        """
        Returns a list of hashtags for this post.
        Uses regex to find Twitter-style hashtags that contain only alphanumeric chars and underscores.
        """
        import re

        if self.content:
            print("Parsing hashtags for post: ", self.content)
            # Find all hashtags using regex
            # Matches # followed by word chars (letters, numbers, underscore)
            # The (?<!\S) ensures the # has whitespace or start-of-string before it
            hashtag_pattern = r"(?<!\S)#([a-zA-Z0-9_]+)"
            matches = re.finditer(hashtag_pattern, self.content)

            for match in matches:
                hashtag = match.group(1)  # group(1) gets just the tag without the #
                print("Hashtag: ", hashtag)
                try:
                    hashtag, created = Hashtag.objects.get_or_create(
                        tag=hashtag.lower(),
                        post=self,
                    )
                except Exception as e:
                    print(f"Error processing hashtag {hashtag}: {e}")

    def save(self, *args, **kwargs):
        # Check for profanity in content
        if not self.is_flagged:  # Only check if not already flagged
            self.is_flagged = check_profanity(self.content)

        self.parse_hashtags()
        super().save(*args, **kwargs)


class Vote(BaseModel):
    """
    Vote model.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    is_upvote = models.BooleanField(default=True)

    def __str__(self):
        vote_type = "Upvote" if self.is_upvote else "Downvote"
        return f"{vote_type} by {self.user_profile} on {self.post.id}"


class SocialNetwork(BaseModel):
    """
    SocialNetwork network model.
    """

    source_node = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="following",
    )  # Follower
    target_node = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="followers",
    )  # Who is being followed

    def __str__(self):
        return f"{self.source_node} → {self.target_node}"


class DigitalTwin(BaseModel):
    """
    Digital twin of a human user.
    """

    persona = models.TextField()
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    api_token = models.CharField(max_length=255, null=True, blank=True)
    llm_url = models.CharField(max_length=255, null=True, blank=True)
    llm_model = models.CharField(max_length=255, null=True, blank=True)
    last_post = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user_profile.username


class Hashtag(BaseModel):
    """
    Hashtag model.
    """

    tag = models.CharField(max_length=255)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

    def __str__(self):
        return f"#{self.tag}, {self.post.id}"


class Notification(BaseModel):
    """
    Notification model.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    event = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user_profile.username} - {self.event}"


class ExperimentInvitation(BaseModel):
    """
    Experiment invitation model.
    """

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    email = models.EmailField()
    is_accepted = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.email} - {self.experiment.name}"


class AuthApiToken(models.Model):
    key = models.CharField(max_length=40, primary_key=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="auth_tokens",
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auth API Token"
        verbose_name_plural = "Auth API Tokens"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(20)
        super().save(*args, **kwargs)

    def __str__(self):  # noqa: DJ012
        return self.key
