import uuid
import hashlib
from django.db import models
from django.contrib.auth import get_user_model

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


class Experiment(BaseModel):
    """
    Experiment model.
    """
    name = models.CharField(max_length=255)
    identifier = models.CharField(max_length=5, unique=True)
    description = models.TextField()
    options = models.JSONField(default=dict)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # This defines what user "owns" this experiment

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
    
    def save(self, *args, **kwargs):
        if not self.identifier:
            self.identifier = self.create_identifier()
        super().save(*args, **kwargs)


class UserProfile(BaseModel):
    """
    User profile model.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255, unique=True)
    username = models.CharField(max_length=255, unique=True)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    banner_picture = models.ImageField(upload_to='banner_pictures/', null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    num_followers = models.IntegerField(default=0)
    num_following = models.IntegerField(default=0)
    is_digital_twin = models.BooleanField(default=False)
    is_collaborator = models.BooleanField(default=False)  # Works with the experiment owner to administer the experiment
    is_moderator = models.BooleanField(default=False)  # Delete posts, ban / report users
    is_banned = models.BooleanField(default=False)  # Cannot post, reply, or view content
    is_private = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
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
            self.experiment.creator == self.user or  # User owns the experiment
            self.is_collaborator or  # User is a collaborator
            self.is_moderator  # User has moderator flag
        )


class UndeletedPostManager(models.Manager):
    def get_queryset(self):
        # Only return posts that are not deleted or from user profiles that are not banned
        return super().get_queryset().filter(is_deleted=False).exclude(user_profile__is_banned=True)


class Post(BaseModel):
    """
    Post model.
    """
    user_profile = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    content = models.TextField()
    parent_post = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    depth = models.IntegerField(default=0)
    num_upvotes = models.IntegerField(default=0)
    num_downvotes = models.IntegerField(default=0)
    num_comments = models.IntegerField(default=0)
    num_shares = models.IntegerField(default=0)  # any repost or quote of this post
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        status = " (Deleted)" if self.is_deleted else ""
        return f"Post by {self.user_profile.username}: {preview}{status}"
    
    all_objects = models.Manager()
    objects = UndeletedPostManager()
    
    def get_comment_count(self):
        """
        Returns the number of posts that have this post as their parent.
        """
        return Post.objects.filter(parent_post=self).count()


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
    source_node = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='following')  # Follower
    target_node = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='followers')  # Who is being followed

    def __str__(self):
        return f"{self.source_node} → {self.target_node}"


class DigitalTwin(BaseModel):
    """
    Digital twin of a human user.
    """
    # name = models.CharField(max_length=100)
    persona = models.TextField()
    # user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    api_token = models.CharField(max_length=255, default='default_token')
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
