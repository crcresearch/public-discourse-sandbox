import random
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Post, DigitalTwin
from .tasks import process_digital_twin_response

@receiver(post_save, sender=Post)
def handle_post(sender, instance, created, **kwargs):
    """
    Signal handler for Post model's post_save signal.
    This will be called whenever a Post is saved, but only processes new posts (created=True).
    For new posts from human users, it triggers digital twin responses.
    
    Args:
        sender: The model class (Post)
        instance: The actual Post instance being saved
        created: Boolean indicating if this is a new record (True) or an update (False)
        **kwargs: Additional keyword arguments
    """
    # Only process new posts from human users that are top-level (not replies)
    if created and not instance.user_profile.is_digital_twin and instance.depth == 0:
        # Get all the active bots for the experiment by filtering through the user_profile relationship
        active_twins = DigitalTwin.objects.filter(
            is_active=True,
            user_profile__experiment=instance.user_profile.experiment
        )
        # Get a random list of twins in length of the queryset
        if len(active_twins) > 0:
            random_length = random.randint(1, len(active_twins))
            random_twins = random.sample(list(active_twins), random_length)
        else:
            random_twins = []
        
        # Define the task to be executed after transaction commit
        def send_tasks():
            for twin in random_twins:
                process_digital_twin_response.delay(str(instance.id), str(twin.id))
        
        # Schedule the tasks to run after the transaction is committed
        transaction.on_commit(send_tasks) 