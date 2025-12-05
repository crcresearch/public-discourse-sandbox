import logging
import random
import time
import uuid
from typing import Any

import openai
from django.conf import settings
from django.utils import timezone

from public_discourse_sandbox.pds_app.models import DigitalTwin
from public_discourse_sandbox.pds_app.models import Post
from public_discourse_sandbox.pds_app.models import Notification
from public_discourse_sandbox.pds_app.utils import send_notification_to_user

"""
DTService Execution Flow:
------------------------

respond_to_post(twin, post)
└── generate_comment(twin, content, post)
    ├── analyze_context(post)
    │   ├── create basic context (post_content, post_id, user, timestamp)
    │   ├── _analyze_sentiment(post.content)
    │   └── _extract_keywords(post.content)
    │
    └── generate_llm_response(post, context, twin)
        ├── template("RESPOND", prompt, twin)
        │   └── get_twin_config(twin)
        │
        └── execute(template)
            ├── _add_to_working_memory(template)
            │   ├── _truncate_memory()
            │   └── _ensure_objective()
            │
            └── OpenAI API Call
                └── Create Post Comment

Working Memory System:
--------------------
- Maintains conversation state
- Max token length: 512
- Truncates automatically when limit reached
"""

# Set up logging
logger = logging.getLogger(__name__)


class DTService:
    """
    Service class that manages digital twin interactions with posts.
    Handles the creation of contextually appropriate responses using LLM.
    """

    def __init__(self):
        logger.info("DTListener initialized")
        self.working_memory = ""
        self.token_counter = 0
        self.max_token_length = 512  # Default value, adjust as needed
        self.current_twin = None  # Add this line to store current twin

    def _add_to_working_memory(self, input_data: str) -> None:
        """
        Maintains a rolling memory of conversation context for the LLM.
        Part of the memory management system that ensures context stays within token limits.

        Flow: Called by execute() before each LLM interaction
        """
        self.working_memory += f" {input_data}"
        self.token_counter += len(input_data.split())

        self._truncate_memory()
        self._ensure_objective()

    def _truncate_memory(self):
        """
        Ensures working memory stays within token limits by removing oldest tokens when exceeded.
        Keeps the most recent max_token_length tokens.

        Flow: Called by _add_to_working_memory() when new content is added
        """
        if self.token_counter > self.max_token_length:
            tokens = self.working_memory.split()[-self.max_token_length :]
            self.working_memory, self.token_counter = (
                " ".join(tokens),
                self.max_token_length,
            )

    def _ensure_objective(self):
        """
        Ensures the digital twin's objective/persona is present in the working memory context.
        Prepends the twin's objective to working memory if it's not already present,
        ensuring the LLM maintains consistent character voice throughout the conversation.
        Updates token counter when objective is added.

        Flow: Called by _add_to_working_memory() as part of memory management system

        Memory Structure:
            - If objective not present: "{objective} {existing_memory}"
            - If objective present: leaves memory unchanged

        Note: Requires self.current_twin to be set. Silently returns if no twin is set,
        as this can happen during initialization or between responses.
        """
        if not self.current_twin:
            return  # Skip if no twin is set

        objective = self.get_twin_config(self.current_twin)["AgentCode"]["objective"]
        if objective not in self.working_memory:
            self.working_memory = f"{objective} {self.working_memory}"
            self.token_counter += len(objective.split())

    def execute(self, template: str, twin: DigitalTwin) -> Any:
        """
        Core LLM interaction method. Sends prompts to OpenAI and manages the conversation memory.
        Acts as the central point for all AI model interactions.

        Flow: Called by generate_llm_response() to get AI responses
        """
        start_time = time.time()
        self._add_to_working_memory(template)

        # Use OpenAI directly instead of self.llm.prompt
        try:
            if twin.api_token:
                api_key = twin.api_token
            else:
                api_key = settings.OPENAI_API_KEY

            if twin.llm_url:
                base_url = twin.llm_url
            else:
                base_url = settings.OPENAI_BASE_URL

            if twin.llm_model:
                llm_model = twin.llm_model
            else:
                llm_model = settings.LLM_MODEL

            client = openai.OpenAI(
                base_url=base_url,
                api_key=api_key,
            )
            response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": self.working_memory},
                ],
            )
            output = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {e!s}")
            output = "Error generating response"

        elapsed_time = time.time() - start_time

        return output

    def _analyze_sentiment(self, text: str) -> str:
        """
        Uses OpenAI to determine the emotional tone of text.
        Returns one of: positive, negative, or neutral.

        Flow: Called by analyze_context() as part of post analysis
        """
        print(f"Analyzing sentiment for text: {text}")
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the sentiment of this text. Respond with just one word: positive, negative, or neutral.",
                    },
                    {"role": "user", "content": text},
                ],
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            print(f"Error analyzing sentiment: {e!s}")
            return "neutral"

    def _extract_keywords(self, text: str) -> list[str]:
        """
        Uses OpenAI to identify 3-5 main topics/themes from the text.
        Returns a list of key terms that represent the content.

        Flow: Called by analyze_context() after sentiment analysis
        """
        print(f"Extracting keywords for text: {text}")
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract 3-5 main keywords from this text. Respond with just the keywords separated by commas.",
                    },
                    {"role": "user", "content": text},
                ],
            )
            keywords = response.choices[0].message.content.strip().split(",")
            return [k.strip() for k in keywords if k.strip()]
        except Exception as e:
            print(f"Error extracting keywords: {e!s}")
            return []

    def analyze_context(self, post: Post) -> dict:
        """
        Creates a comprehensive context dictionary for a post.
        Combines basic post metadata with AI-derived insights (sentiment and keywords).
        Handles API failures gracefully by providing neutral defaults.

        Flow: Called by generate_comment() as first step in response generation
        """
        if post.repost_source:
            post_content = post.repost_source.content
        else:
            post_content = post.content
        try:
            # Create a simpler context without API calls first
            context = {
                "post_content": post_content,
                "post_id": post.id,
                "user": post.user_profile.username
                if post.user_profile.username
                else "unknown",
                "timestamp": post.created_date.isoformat()
                if post.created_date
                else None,
            }
            print(f"Basic context created: {context}")

            # Try to add sentiment and keywords if API is working
            try:
                context["sentiment"] = self._analyze_sentiment(post_content)
                context["keywords"] = self._extract_keywords(post_content)
            except Exception as api_error:
                print(f"API-related error in context analysis: {api_error!s}")
                context["sentiment"] = "neutral"
                context["keywords"] = []

            print(f"Context analysis complete: {context}")
            return context
        except Exception as e:
            print(f"Error analyzing context: {e!s}")
            return {
                "post_content": post_content,
                "error": str(e),
            }

    def get_twin_config(self, twin: DigitalTwin) -> dict:
        """
        Builds configuration dictionary for a digital twin's behavior.
        Defines the twin's identity, objectives, and control flow for responses.

        Flow: Called by template() to get twin-specific response parameters
        """
        return {
            "AgentCode": {
                "name": twin.user_profile.username,
                "objective": f"You are {twin.user_profile.username}. {twin.persona}",
                "control_flow": {
                    "BEGIN": "ANALYZE",
                    "ANALYZE": "RESPOND",
                    "RESPOND": "END",
                },
                "ANALYZE": "Analyze this post: {0}",
                "RESPOND": "{0}",
            },
            "LLM": {
                "prompt_model": "openai/gpt-3.5-turbo",
                "action_model": "openai/gpt-3.5-turbo",
                "api_key": settings.OPENAI_API_KEY,
                "functions": [],
                "system_message": twin.persona,
                "max_retries": 3,
            },
        }

    def template(self, phase: str, input_data: Any, twin: DigitalTwin) -> Any:
        """
        Formats prompts according to the twin's configuration and current phase.
        Ensures responses align with the twin's persona and objectives.

        Flow: Called by generate_llm_response() to format prompts for the LLM
        """
        # print(f"Template for {phase} with input: {input_data}")
        if phase not in self.get_twin_config(twin)["AgentCode"]:
            raise ValueError(f"Undefined phase: {phase}")
        return self.get_twin_config(twin)["AgentCode"][phase].format(input_data)

    def generate_llm_response(
        self, post: Post, context: dict = None, twin: DigitalTwin = None
    ) -> str:
        """
        Creates contextually appropriate responses using the LLM.
        Handles retry logic for API failures and ensures responses stay within length limits.
        Uses twin's persona to maintain consistent character voice.

        Flow: Called by generate_comment() after context analysis
        """
        print(f"Generating response for post: {post.id}")
        try:
            self.current_twin = twin  # Set the current twin
            if not context:
                context = self.analyze_context(post)

            prompt = f"""As {twin.user_profile.username} with the following persona: {twin.persona}

            You are responding to this post:
            "{post.content}"

            Context:
            - Post author: {context.get('user', 'unknown')}
            - Sentiment: {context.get('sentiment', 'neutral')}
            - Keywords: {', '.join(context.get('keywords', [])) if context.get('keywords') else 'none'}

            Generate a natural, contextually appropriate response that stays true to your persona.
            Keep the response concise (1-2 sentences) and engaging.
            """

            print(f"Sending prompt to LLM for {twin.user_profile.username}")
            for attempt in range(3):  # Try up to 3 times
                try:
                    template = self.template("RESPOND", prompt, twin)
                    response = self.execute(template, twin)
                    if response:
                        print(
                            f"Generated response on attempt {attempt + 1}: {response}"
                        )
                        # Clean up the response
                        response = response.strip().strip('"').strip()
                        if len(response) > 280:  # Twitter-like character limit
                            response = response[:277] + "..."
                        return response
                except Exception as api_error:
                    print(f"API error on attempt {attempt + 1}: {api_error!s}")
                    if attempt == 2:  # Last attempt
                        raise
            return None

        except Exception as e:
            print(f"Error generating response: {e!s}")
            return None
        finally:
            self.current_twin = None  # Clear the current twin when done

    def generate_comment(self, twin: DigitalTwin, content: str, post: Post) -> str:
        """
        Orchestrates the full response generation process.
        Coordinates context analysis and LLM response generation.
        Provides detailed logging of the generation process.

        Flow: Called by respond_to_post() to create twin's response
        """
        context = self.analyze_context(post)
        print("Generating response...")
        response = self.generate_llm_response(post, context, twin)
        print(f"Generated response: {response}")

        return response

    def respond_to_post(self, twin, post):
        """
        Entry point for digital twin interactions.
        Manages the full flow from content analysis to response creation.
        Creates and stores the final comment in the database.

        Args:
            twin (DigitalTwin): The digital twin that will respond
            post (Post or UUID): The post to respond to, can be Post object or UUID

        Flow: Main entry point called by external code
        """
        try:
            # First ensure we have a valid post object
            if isinstance(post, str) or isinstance(post, uuid.UUID):
                try:
                    post = Post.objects.get(id=post)
                except Post.DoesNotExist:
                    logger.error(f"Post with id {post} not found")
                    return []

            print(f"Responding to content: {post.content[:100]}")
            logger.info(f"""
            Attempting to respond to content:
            Content: {post.content[:100]}
            Post ID: {post.id}
            """)

            responses = []
            # Generate digital twin response
            logger.info(
                f"Generating comment using digital twin {twin.user_profile.username}"
            )
            comment_content = self.generate_comment(
                twin=twin,
                content=post.content,
                post=post,
            )

            if not comment_content:
                logger.error(
                    f"Failed to generate comment content for digital twin {twin.user_profile.username}"
                )

            # Create the comment
            comment = Post.objects.create(
                user_profile=twin.user_profile,
                parent_post=post,
                content=comment_content,
                experiment=post.experiment,
                depth=post.depth + 1,
            )

            # Save the comment again to perform hashtag parsing after the post ID exists
            comment.save()

            Notification.objects.create(
                user_profile=post.user_profile,
                event="post_replied",
                content=f"@{twin.user_profile.username} replied to your post",
            )
            logger.info(f"Created digital twin comment: {comment.content[:50]}...")
            responses.append(comment)

            return responses

        except Exception as e:
            logger.error(
                f"Error in twin {twin.user_profile.username} response: {e!s}",
                exc_info=True,
            )

    def should_twin_post(self, twin: DigitalTwin) -> bool:
        """
        Determines if a digital twin should post based on activity patterns.
        Uses probabilistic approach based on recent post history and time since last post.

        Args:
            twin (DigitalTwin): The digital twin to check

        Returns:
            bool: True if the twin should post, False otherwise
        """
        skip_probability = 0.0

        # Factor 1: Time since last post
        if twin.last_post:
            hours_since_last = (timezone.now() - twin.last_post).total_seconds() / 3600
            if hours_since_last < 1:
                skip_probability += 0.8  # High chance to skip if posted in last hour
            elif hours_since_last < 4:
                skip_probability += 0.5  # Medium chance if posted in last 4 hours
            elif hours_since_last < 8:
                skip_probability += 0.3  # Lower chance if posted in last 8 hours

        # Factor 2: Recent post ratio
        recent_posts = Post.objects.filter(
            experiment=twin.user_profile.experiment,
            parent_post=None,  # Only top-level posts
            created_date__gte=timezone.now() - timezone.timedelta(hours=24),
        ).order_by("-created_date")[:20]

        if recent_posts:
            twin_post_count = sum(
                1
                for post in recent_posts
                if post.user_profile_id == twin.user_profile_id
            )
            twin_ratio = twin_post_count / len(recent_posts)
            skip_probability += min(0.7, twin_ratio)  # Up to 0.7 based on ratio

        # Make skip decision (return False if should skip)
        if random.random() < skip_probability:
            logger.info(
                f"Digital twin {twin.user_profile.username} chose not to post (p={skip_probability:.2f})"
            )
            return False

        return True

    def get_recent_post_context(
        self, twin: DigitalTwin, max_posts: int = 10
    ) -> list[dict]:
        """
        Gets context from recent posts to inform the twin's new post.
        Excludes the twin's own posts to avoid self-reference.

        Args:
            twin (DigitalTwin): The digital twin creating the post
            max_posts (int): Maximum number of posts to include in context

        Returns:
            List[Dict]: List of post context dictionaries
        """
        recent_posts = Post.objects.filter(
            experiment=twin.user_profile.experiment,
            parent_post=None,  # Only top-level posts
            created_date__gte=timezone.now() - timezone.timedelta(hours=24),
        ).order_by("-created_date")[:20]

        post_contexts = []
        for post in recent_posts[:max_posts]:
            # Skip posts by this twin to avoid self-reference
            if post.user_profile_id != twin.user_profile_id:
                post_contexts.append(
                    {
                        "author": post.user_profile.username,
                        "content": post.content,
                        "timestamp": post.created_date.isoformat(),
                    }
                )

        return post_contexts

    def determine_post_length(self) -> dict:
        """
        Randomly determines post length based on a probability distribution.
        Uses weighted random selection to vary post lengths naturally.

        Returns:
            Dict: Selected length category with range and name
        """
        # Define post length categories with probability distribution
        length_distribution = [
            {"name": "very short", "range": (20, 80), "probability": 0.35},
            {"name": "short", "range": (80, 140), "probability": 0.35},
            {"name": "medium", "range": (140, 200), "probability": 0.20},
            {"name": "long", "range": (200, 280), "probability": 0.10},
        ]

        # Randomly select length category based on probability distribution
        rand_val = random.random()
        cumulative_prob = 0

        for length_cat in length_distribution:
            cumulative_prob += length_cat["probability"]
            if rand_val <= cumulative_prob:
                min_chars, max_chars = length_cat["range"]
                target_length = random.randint(min_chars, max_chars)

                # Add target_length to the returned dictionary
                result = length_cat.copy()
                result["target_length"] = target_length

                logger.info(
                    f"Selected {length_cat['name']} post length ({min_chars}-{max_chars} chars)"
                )
                return result

        # Fallback to short length if something goes wrong
        return {"name": "short", "range": (80, 140), "target_length": 100}

    def generate_original_post_content(
        self, twin: DigitalTwin, post_contexts: list[dict]
    ) -> str:
        """
        Generates original post content using the LLM based on the twin's persona.
        Handles the full prompt creation and LLM interaction for new posts.

        Args:
            twin (DigitalTwin): The digital twin creating the post
            post_contexts (List[Dict]): Context from recent posts

        Returns:
            str: The generated post content
        """
        try:
            self.current_twin = twin  # Set the current twin

            # Format context posts
            context_text = ""
            if post_contexts:
                context_text = "Recent posts in the community:\n"
                for i, post in enumerate(post_contexts, 1):
                    context_text += f'{i}. @{post['author']}: "{post['content']}"\n'

            # Get length parameters
            length_params = self.determine_post_length()
            min_chars, max_chars = length_params["range"]
            target_length = length_params["target_length"]

            # Construct the prompt with specific length guidance
            prompt = f"""You are {twin.user_profile.username}, with the following persona:
{twin.persona}

Create a new post based on your persona. This should be an original thought, not a reply to anyone specific.

{context_text}

Instructions:
1. Your post should be approximately {target_length} characters long (between {min_chars}-{max_chars} characters)
2. Write as your persona would write naturally
3. Don't explicitly reference being an AI or digital twin
4. You can reference recent community discussions if relevant
5. Your post should feel authentic and natural
6. Some posts should be very concise, others more detailed - vary your style
7. Use natural language patterns that reflect how real people write social media posts
8. If you decide to mention another user, use their username with an @ symbol immediately preceding it

Output only the text of the post, with no additional commentary or explanation.
"""

            # Use the OpenAI client with the twin's configured API details
            if twin.api_token:
                api_key = twin.api_token
            else:
                api_key = settings.OPENAI_API_KEY

            if twin.llm_url:
                base_url = twin.llm_url
            else:
                base_url = settings.OPENAI_BASE_URL

            if twin.llm_model:
                llm_model = twin.llm_model
            else:
                llm_model = settings.LLM_MODEL

            client = openai.OpenAI(
                base_url=base_url,
                api_key=api_key,
            )

            # Make the API call
            response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a digital twin participating in social media discussions. Your goal is to create authentic, natural posts that reflect your assigned persona and engage meaningfully with the community.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            # Extract and clean the content
            content = response.choices[0].message.content.strip().strip('"').strip()

            # If content exceeds maximum allowed length, trim it
            if len(content) > 280:
                content = content[:277] + "..."

            # Log the actual content length for monitoring
            logger.info(
                f"Generated post with {len(content)} characters (target was {target_length})"
            )

            return content

        except Exception as e:
            logger.error(
                f"Error in generate_original_post_content: {e!s}", exc_info=True
            )
            return None
        finally:
            self.current_twin = None  # Clear the current twin when done

    def create_original_post(self, twin: DigitalTwin, force: bool = False) -> str:
        """
        Entry point for digital twin original post creation.
        Manages the full flow from context gathering to post creation.
        Updates the twin's last_post timestamp after creating the post.

        Args:
            twin (DigitalTwin): The digital twin that will create the post
            force (bool, optional): If True, bypasses the should_post check. Default is False.

        Returns:
            str: ID of the created post, or None on failure
        """
        try:
            logger.info(
                f"Starting original post generation for {twin.user_profile.username}"
            )

            # Check if the twin should post based on activity, unless force=True
            if not force and not self.should_twin_post(twin):
                logger.info(
                    f"Post generation skipped for {twin.user_profile.username} due to should_post check"
                )
                return None

            # Get context from recent posts
            post_contexts = self.get_recent_post_context(twin)

            # Generate the post content using LLM
            post_content = self.generate_original_post_content(twin, post_contexts)

            if not post_content:
                logger.error(
                    f"Failed to generate post content for {twin.user_profile.username}"
                )
                return None

            # Create a new post from the digital twin
            # Important: Use create() + save() to make sure the post ID is set before the hashtag parsing runs
            new_post = Post.objects.create(
                user_profile=twin.user_profile,
                experiment=twin.user_profile.experiment,
                content=post_content,
                depth=0,  # Top-level post
            )

            # Save the post again to perform hashtag parsing after the post ID exists
            new_post.save()

            # Update the last_post timestamp for the twin
            twin.last_post = timezone.now()
            twin.save(update_fields=["last_post", "last_modified"])

            logger.info(
                f"Created new post by {twin.user_profile.username}: {new_post.id}"
            )
            return str(new_post.id)

        except Exception as e:
            logger.error(f"Error creating original post: {e!s}", exc_info=True)
            return None
