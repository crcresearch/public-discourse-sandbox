from celery import shared_task
from .dt_service import DTService
from .models import Post
import logging
import time
import random
from .models import DigitalTwin

logger = logging.getLogger(__name__)

def get_random_digitial_twins(count=1, exclude_twin=None):
    """Get random active twins, optionally excluding a specific twin"""
    active_twins = DigitalTwin.objects.filter(is_active=True)
    if exclude_twin:
        active_twins = active_twins.exclude(id=exclude_twin.id)
    
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
def process_bot_response(post_id):
    """
    Celery task to process bot response to a post.
    """
    logger.info(f"Starting bot response processing for post {post_id}")
    print(f"Starting bot response processing for post {post_id}")

    num_responses = 1

    try:
        twins = get_random_digitial_twins(count=num_responses)
        if not twins:
            logger.warning("No active digital twins available")
            return

        # Get the post
        post = Post.objects.get(id=post_id)
        logger.info(f"Found post by user {post.user_profile.username}")
        
        # Initialize the digital twin service
        dt_service = DTService()

        for twin in twins:
            logger.info("Waiting 10 seconds for response...")
            # time.sleep(10)
            response = dt_service.respond_to_post(twin,post)
            logger.info(f"Generated first digital twin response to post {post_id}")
        
        logger.info(f"Successfully processed all bot responses for post {post_id}")
        
    except Post.DoesNotExist:
        logger.error(f"Post with id {post_id} not found")
    except Exception as e:
        logger.error(f"Error processing bot response: {str(e)}", exc_info=True) 