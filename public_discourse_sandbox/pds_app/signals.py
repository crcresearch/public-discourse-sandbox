from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Post
from .tasks import process_bot_response

@receiver(post_save, sender=Post)
def handle_post(sender, instance, created, **kwargs):
    """
    Signal handler for Post model's post_save signal.
    This will be called whenever a Post is saved.
    """
    post = instance
    print(f"----Processing post from user: {post.user_profile.username} (is_bot: {post.user_profile.is_bot})----")
    
    # Only process non-bot posts
    if not post.user_profile.is_bot:
        # Trigger the Celery task asynchronously
        process_bot_response.delay(str(post.id))  # Convert UUID to string for serialization 