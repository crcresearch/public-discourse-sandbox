from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Post
from .tasks import process_digital_twin_response

@receiver(post_save, sender=Post)
def handle_post(sender, instance, created, **kwargs):
    """
    Signal handler for Post model's post_save signal.
    This will be called whenever a Post is saved.
    """
    if created:  # Only process new posts
        def send_task():
            process_digital_twin_response.delay(str(instance.id))
        
        transaction.on_commit(send_task) 