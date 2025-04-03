from celery import shared_task
from .dt_service import DTService
from .models import Post
import logging
import time

logger = logging.getLogger(__name__)

@shared_task
def process_bot_response(post_id):
    """
    Celery task to process bot response to a post.
    Implements delayed responses with sequential timing:
    - First twin: 10 seconds after tweet
    - Second twin: 30 seconds after first twin (40s total)
    - Third twin: 10 seconds after second twin (50s total)
    """
    logger.info(f"Starting bot response processing for post {post_id}")
    try:
        # Get the post
        post = Post.objects.get(id=post_id)
        logger.info(f"Found post by user {post.user_profile.username}")
        
        # Initialize the digital twin service
        dt_service = DTService()
        
        # First twin response after 10 seconds
        logger.info("Waiting 10 seconds for first response...")
        time.sleep(10)
        first_response = dt_service.respond_to_content(
            post.content,
            post,
            parent_comment=None,
            num_responses=1
        )
        logger.info(f"Generated first digital twin response to post {post_id}")

        # Second twin response after 30 more seconds
        logger.info("Waiting 30 seconds for second response...")
        time.sleep(30)
        second_response = dt_service.respond_to_content(
            post.content,
            post,
            parent_comment=None,
            num_responses=1
        )
        logger.info(f"Generated second digital twin response to post {post_id}")

        # Third twin response after 10 more seconds
        logger.info("Waiting 10 seconds for third response...")
        time.sleep(10)
        third_response = dt_service.respond_to_content(
            post.content,
            post,
            parent_comment=None,
            num_responses=1
        )
        logger.info(f"Generated third digital twin response to post {post_id}")
        
        logger.info(f"Successfully processed all bot responses for post {post_id}")
        
    except Post.DoesNotExist:
        logger.error(f"Post with id {post_id} not found")
    except Exception as e:
        logger.error(f"Error processing bot response: {str(e)}", exc_info=True) 