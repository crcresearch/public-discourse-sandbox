import logging
import time
import openai
from typing import Any, Dict, List
from django.conf import settings
import uuid
from django.core.exceptions import ObjectDoesNotExist

from public_discourse_sandbox.pds_app.models import DigitalTwin, Post

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
            tokens = self.working_memory.split()[-self.max_token_length:]
            self.working_memory, self.token_counter = ' '.join(tokens), self.max_token_length

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


    def execute(self, template: str) -> Any:
        """
        Core LLM interaction method. Sends prompts to OpenAI and manages the conversation memory.
        Acts as the central point for all AI model interactions.

        Flow: Called by generate_llm_response() to get AI responses
        """
        start_time = time.time()
        self._add_to_working_memory(template)
        
        # Use OpenAI directly instead of self.llm.prompt
        try:
            client = openai.OpenAI(
                base_url=settings.OPENAI_BASE_URL,
                api_key=settings.OPENAI_API_KEY
            )
            response = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": self.working_memory}
                ]
            )
            output = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
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
                    {"role": "system", "content": "Analyze the sentiment of this text. Respond with just one word: positive, negative, or neutral."},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            print(f"Error analyzing sentiment: {str(e)}")
            return "neutral"

    def _extract_keywords(self, text: str) -> List[str]:
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
                    {"role": "system", "content": "Extract 3-5 main keywords from this text. Respond with just the keywords separated by commas."},
                    {"role": "user", "content": text}
                ]
            )
            keywords = response.choices[0].message.content.strip().split(',')
            return [k.strip() for k in keywords if k.strip()]
        except Exception as e:
            print(f"Error extracting keywords: {str(e)}")
            return []

    def analyze_context(self, post: Post) -> Dict:
        """
        Creates a comprehensive context dictionary for a post.
        Combines basic post metadata with AI-derived insights (sentiment and keywords).
        Handles API failures gracefully by providing neutral defaults.

        Flow: Called by generate_comment() as first step in response generation
        """
        try:
            # Create a simpler context without API calls first
            context = {
                'post_content': post.content,
                'post_id': post.id,
                'user': post.user_profile.username if post.user_profile.username else 'unknown',
                'timestamp': post.created_date.isoformat() if post.created_date else None
            }
            print(f"Basic context created: {context}")
            
            # Try to add sentiment and keywords if API is working
            try:
                context['sentiment'] = self._analyze_sentiment(post.content)
                context['keywords'] = self._extract_keywords(post.content)
            except Exception as api_error:
                print(f"API-related error in context analysis: {str(api_error)}")
                context['sentiment'] = 'neutral'
                context['keywords'] = []
                
            print(f"Context analysis complete: {context}")
            return context
        except Exception as e:
            print(f"Error analyzing context: {str(e)}")
            return {
                'post_content': post.content,
                'error': str(e)
            }

    def get_twin_config(self, twin: DigitalTwin) -> Dict:
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
                    "RESPOND": "END"
                },
                "ANALYZE": "Analyze this post: {0}",
                "RESPOND": "{0}"
            },
            "LLM": {
                "prompt_model": "openai/gpt-3.5-turbo",
                "action_model": "openai/gpt-3.5-turbo",
                "api_key": settings.OPENAI_API_KEY,
                "functions": [],
                "system_message": twin.persona,
                "max_retries": 3
            }
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

    def generate_llm_response(self, post: Post, context: Dict = None, twin: DigitalTwin = None) -> str:
        """
        Creates contextually appropriate responses using the LLM.
        Handles retry logic for API failures and ensures responses stay within length limits.
        Uses twin's persona to maintain consistent character voice.

        Flow: Called by generate_comment() after context analysis
        """
        print(f"Generating response for pst: {post.id}")
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
                    response = self.execute(template)
                    if response:
                        print(f"Generated response on attempt {attempt + 1}: {response}")
                        # Clean up the response
                        response = response.strip().strip('"').strip()
                        if len(response) > 280:  # Twitter-like character limit
                            response = response[:277] + "..."
                        return response
                except Exception as api_error:
                    print(f"API error on attempt {attempt + 1}: {str(api_error)}")
                    if attempt == 2:  # Last attempt
                        raise
            return None
            
        except Exception as e:
            print(f"Error generating response: {str(e)}")
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
            logger.info(f"Generating comment using digital twin {twin.user_profile.username}")
            comment_content = self.generate_comment(
                twin=twin, 
                content=post.content,
                post=post
            )
            
            if not comment_content:
                logger.error(f"Failed to generate comment content for digital twin {twin.user_profile.username}")

            # Currently only responding to top-level posts made by human users
            # TODO: Move this check to the signal handler?
            if not post.user_profile.is_bot and not post.parent_post:  # TODO: handle nested replies

                # Create the comment
                comment = Post.objects.create(
                    user_profile=twin.user_profile,
                    parent_post=post,
                    content=comment_content,
                    experiment=post.experiment
                )
                
                logger.info(f"Created digital twin comment: {comment.content[:50]}...")
                responses.append(comment)

            return responses

        except Exception as e:
            logger.error(f"Error in twin {twin.user_profile.username} response: {str(e)}", exc_info=True)
