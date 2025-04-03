import random
import logging
import time
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from public_discourse_sandbox.pds_app.models import DigitalTwin, Post


# Set up logging
logger = logging.getLogger(__name__)

# @receiver(post_save, sender=Post)
# def create_post(sender, instance, created, **kwargs):
#     if created:
#         Post.objects.create(digital_twin=instance)


class DTListener:
    def __init__(self):
        logger.info("DTListener initialized")

    # def get_agent(self, twin: DigitalTwin) -> BotAgent:
    #     """Get or create agent for bot"""
    #     print(f"Getting agent for bot: {bot.name}")
    #     if bot.id not in self.agents:
    #         print(f"Creating new agent for bot: {bot.name}")
    #         self.agents[bot.id] = BotAgent(bot)
    #     return self.agents[bot.id]
    
    def delayed_bot_response(self, post_id):
        """Function to handle delayed bot responses with sequential timing:
        - First bot: 10 seconds after tweet
        - Second bot: 30 seconds after first bot (40s total)
        - Third bot: 10 seconds after second bot (50s total)
        """
        try:
            # Get the tweet
            post = Post.objects.get(id=post_id)

            # First bot response after 10 seconds
            time.sleep(10)
            first_response = self.respond_to_content(
                post.content,
                post,
                parent_comment=None,
                num_responses=1
            )
            logger.info(f"Generated first digital twin response to post {post_id}")

            # Second bot response after 30 more seconds
            time.sleep(30)
            second_response = self.respond_to_content(
                post.content,
                post,
                parent_comment=None,
                num_responses=1
            )
            logger.info(f"Generated second digital twin response to post {post_id}")

            # Third bot response after 10 more seconds
            time.sleep(10)
            third_response = self.respond_to_content(
                post.content,
                post,
                parent_comment=None,
                num_responses=1
            )
            logger.info(f"Generated third digital twin response to post {post_id}")

        except Exception as e:
            logger.error(f"Error in delayed digital twin response for post {post_id}: {str(e)}", exc_info=True)


    @receiver(post_save, sender=Post)
    def handle_post(self, post: Post):
        print(f"----Processing post from user: {post.user_profile.username} (is_bot: {post.user_profile.is_bot})----")
        # # if post.parent_post is None:
        # if post.user_profile.is_bot:
        #     return

        # print(f"----Processing post from user: {post.user_profile.username} (is_bot: {post.user_profile.is_bot})----")
        # logger.info(f"Processing post from user: {post.user_profile.username} (is_bot: {post.user_profile.is_bot})")
        
        # # Get random bots for responses
        # twins = self.get_random_digitial_twins(count=2)
        # if not twins:
        #     logger.warning("No active digital twins available")
        #     return []

        # self.delayed_bot_response(post.id)

    def get_random_digitial_twins(self, count=1, exclude_twin=None):
        """Get random active bots, optionally excluding a specific bot"""
        active_twins = DigitalTwin.objects.filter(is_active=True)
        if exclude_twin:
            active_twins = active_twins.exclude(id=exclude_twin.id)
        
        twin_count = active_twins.count()
        logger.info(f"Found {twin_count} eligible active bots")
        
        if active_twins == 0:
            return []
            
        # Get exactly the specified number of bots, or all available if less
        count = min(count, active_twins)
        selected_twins = random.sample(list(active_twins), count)
        
        for twin in selected_twins:
            logger.info(f"Selected twin: {twin.name} (ID: {twin.id})")
        
        return selected_twins

    def analyze_sentiment(self, content: str) -> float:
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Analyze the sentiment of the following text and return a score between -1 (negative) and 1 (positive)."},
                    {"role": "user", "content": content}
                ],
                max_tokens=10,
                temperature=0
            )
            sentiment = float(response.choices[0].message.content.strip())
            
            # Log sentiment analysis
            self.logger.log_activity(
                bot_name='sentiment_analyzer',
                activity_type='sentiment_analysis',
                content=content,
                response=str(sentiment)
            )
            
            return sentiment
        except Exception as e:
            self.logger.log_activity(
                bot_name='sentiment_analyzer',
                activity_type='error',
                content=content,
                metadata={'error': str(e)}
            )
            return 0.0 

    def generate_comment(self, twin: DigitalTwin, content: str, post: Post) -> str:
        try:
            print(f"\nGenerating comment for bot {twin.name} on post: {post.id}")
            print(f"Tweet content: {content}")
            print(f"Bot persona: {twin.persona[:100]}...")  # Print first 100 chars of persona
            
            # # Get twin's agent
            # agent = self.get_agent(twin)
            # print("Got twin agent")
            
            # Analyze context
            print("Analyzing context...")
            context = self.analyze_context(post)
            print(f"Context analysis result: {context}")
            
            # Generate response
            print("Generating response...")
            response = self.generate_response(post, context)
            print(f"Generated response: {response}")
            
            # Log activity
            self.logger.log_activity(
                bot_name=twin.name,
                activity_type='generated_response',
                content=content,
                response=response,
                metadata={'context': context}
            )
            print("Activity logged")
            
            return response

        except Exception as e:
            print(f"Error in generate_comment: {str(e)}")
            logger.error(f"Error generating comment for twin {twin.name}", exc_info=True)
            self.logger.log_activity(
                twin_name=twin.name,
                activity_type='error',
                content=content,
                metadata={'error': str(e)}
            )
            return None

    def respond_to_content(self, content, post, parent_comment=None, num_responses=2):
        """Generate bot responses to content"""
        logger.info(f"""
        Attempting to respond to content:
        Content: {content[:100]}
        Post ID: {post.id}
        Parent Comment: {parent_comment.id if parent_comment else 'None'}
        Number of responses: {num_responses}
        """)

        # Get random bots for responses
        twins = self.get_random_digitial_twins(count=num_responses)
        if not twins:
            logger.warning("No active digital twins available")
            return []

        responses = []
        for twin in twins:
            try:
                # Stop if we've reached the requested number of responses
                if len(responses) >= num_responses:
                    break

                # Generate bot response
                logger.info(f"Generating comment using bot {twin.name}")
                comment_content = self.generate_comment(
                    twin=twin, 
                    content=content,
                    post=post
                )
                
                if not comment_content:
                    logger.error(f"Failed to generate comment content for bot {twin.name}")
                    continue

                # Create the comment
                comment = Post.objects.create(
                    user_profile=twin.user_profile,
                    parent_post=post,
                    content=comment_content,
                )

                # # Only increment comment count for top-level bot responses to tweets
                # # Do not increment for bot responses to comments
                # if not parent_comment:
                #     # Use update to avoid race conditions
                #     Tweet.objects.filter(id=tweet.id).update(
                #         tweet_comment_amount=F('tweet_comment_amount') + 1
                #     )
                #     # Refresh the tweet object
                #     tweet.refresh_from_db()
                
                logger.info(f"Created digital twin comment: {comment.content[:50]}...")
                responses.append(comment)

            except Exception as e:
                logger.error(f"Error in twin {twin.name} response: {str(e)}", exc_info=True)

        return responses
