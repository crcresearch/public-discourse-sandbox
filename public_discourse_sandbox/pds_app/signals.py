from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Post
from .dt_service import DTService

@receiver(post_save, sender=Post)
def handle_post(sender, instance, created, **kwargs):
    """
    Signal handler for Post model's post_save signal.
    This will be called whenever a Post is saved.
    """
    post = instance
    print(f"----Processing post from user: {post.user_profile.username} (is_bot: {post.user_profile.is_bot})----")
    
    # Uncomment the following code if you want to process the post with the digital twin service
    dt_service = DTService()
    dt_service.delayed_digital_twin_response(post) 