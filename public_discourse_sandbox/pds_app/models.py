import uuid
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
    description = models.TextField()
    options = models.JSONField(default=dict)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.name}"


class UserProfile(BaseModel):
    """
    User profile model.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=255, unique=True)
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    banner_picture = models.ImageField(upload_to='banner_pictures/', null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    num_followers = models.IntegerField(default=0)
    num_following = models.IntegerField(default=0)
    is_bot = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    def __str__(self):
        bot_status = " (Bot)" if self.is_bot else ""
        return f"{self.username}{bot_status}"


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


class Bot(BaseModel):
    # name = models.CharField(max_length=100)
    persona = models.TextField()
    # user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    api_token = models.CharField(max_length=255, default='default_token')
    last_post = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user_profile.username
