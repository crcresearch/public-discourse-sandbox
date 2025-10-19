import logging
import random

from celery import shared_task
from django.core import management

from .dt_service import DTService
from .models import DigitalTwin
from .models import Post

logger = logging.getLogger(__name__)

def get_random_digitial_twins(count=1, exclude_twin=None, experiment_id=None):
    """Get random active twins, optionally excluding a specific twin and/or filtering by experiment"""
    active_twins = DigitalTwin.objects.filter(is_active=True)
    if exclude_twin:
        active_twins = active_twins.exclude(id=exclude_twin.id)

    # Filter by experiment if provided
    if experiment_id:
        active_twins = active_twins.filter(user_profile__experiment_id=experiment_id)

    twin_count = active_twins.count()
    logger.info(f"Found {twin_count} eligible active twins")

    if twin_count == 0:
        return []

    # Get exactly the specified number of twins, or all available if less
    count = min(count, twin_count)
    selected_twins = random.sample(list(active_twins), count)

    for twin in selected_twins:
        logger.info(f"Selected twin: {twin.user_profile.username} (ID: {twin.id})")

    return selected_twins

@shared_task
def process_digital_twin_response(post_id: str, twin_id: str):
    """
    Celery task to process bot response to a post.
    Args:
        post_id (str): UUID of the post to respond to
        twin_id (str): UUID of the digital twin that will respond
    """
    logger.info(f"Starting bot response processing for post {post_id} with twin {twin_id}")
    print(f"Starting bot response processing for post {post_id} with twin {twin_id}")

    try:
        # First fetch the post and twin using their IDs
        try:
            post = Post.objects.get(id=post_id)
            twin = DigitalTwin.objects.get(id=twin_id)
        except (Post.DoesNotExist, DigitalTwin.DoesNotExist) as e:
            logger.error(f"Post or Twin not found: {e!s}")
            return

        # Initialize the digital twin service
        dt_service = DTService()

        # Generate response using the specific twin
        response = dt_service.respond_to_post(twin, post)
        logger.info(f"Generated digital twin response to post {post.id}")

    except Exception as e:
        logger.error(f"Error processing bot response: {e!s}", exc_info=True)

@shared_task
def generate_digital_twin_post(experiment_id=None, force=False):
    """
    Celery task to make a DigitalTwin generate a new original post (not a reply).

    Args:
        experiment_id (str, optional): UUID of the experiment to filter twins by.
            If None, will select from all active twins across experiments.
        force (bool, optional): If True, bypasses the should_post check. Default is False.
    """
    logger.info(f"Starting digital twin post generation. Experiment filter: {experiment_id}, Force: {force}")

    try:
        # Get a random digital twin
        twins = get_random_digitial_twins(count=1, experiment_id=experiment_id)

        if not twins:
            logger.warning(f"No active digital twins found for experiment_id: {experiment_id}")
            return None

        twin = twins[0]
        logger.info(f"Selected digital twin: {twin.user_profile.username}")

        # Initialize the digital twin service
        dt_service = DTService()

        # Use the service to create an original post, passing the force parameter
        post_id = dt_service.create_original_post(twin, force=force)

        return post_id

    except Exception as e:
        logger.error(f"Error generating digital twin post: {e!s}", exc_info=True)
        return None

@shared_task
def process_email_notifications():
    try:
        management.call_command("process_notifications")
    except Exception:
        logger.error("Error while processing email notifications: {e!s}", exc_info=True)
