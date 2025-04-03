import logging
import time
import openai
from typing import Any, Dict, List
from django.conf import settings

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
    def __init__(self):
        logger.info("DTListener initialized")
        self.working_memory = ""
        self.token_counter = 0
        self.max_token_length = 512  # Default value, adjust as needed

    def _add_to_working_memory(self, input_data: str) -> None:
        """Adds the input_data to working memory, considering token constraints."""
        self.working_memory += f" {input_data}"
        self.token_counter += len(input_data.split())
        
        self._truncate_memory()
        self._ensure_objective()

    def _truncate_memory(self):
        if self.token_counter > self.max_token_length:
            tokens = self.working_memory.split()[-self.max_token_length:]
            self.working_memory, self.token_counter = ' '.join(tokens), self.max_token_length

    def execute(self, template: str) -> Any:
        """Executes a particular phase using sub-agents."""
        start_time = time.time()
        self._add_to_working_memory(template)
        
        # Use OpenAI directly instead of self.llm.prompt
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
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
        """Analyze text sentiment"""
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
        """Extract key topics from text"""
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
        """Analyze the context of a post"""
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
        # print(f"Template for {phase} with input: {input_data}")
        if phase not in self.get_twin_config(twin)["AgentCode"]:
            raise ValueError(f"Undefined phase: {phase}")
        return self.get_twin_config(twin)["AgentCode"][phase].format(input_data)

    def generate_llm_response(self, post: Post, context: Dict = None, twin: DigitalTwin = None) -> str:
        """Generate a response to a post"""
        print(f"Generating response for pst: {post.id}")
        try:
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

    def generate_comment(self, twin: DigitalTwin, content: str, post: Post) -> str:
        print(f"Generating comment for digital twin {twin.user_profile.username} on post: {post.id}")
        try:
            print(f"\nGenerating comment for digital twin {twin.user_profile.username} on post: {post.id}")
            print(f"Post content: {content}")
            print(f"Digital twin persona: {twin.persona[:100]}...")  # Print first 100 chars of persona
            
            # Analyze context
            print("Analyzing context...")
            context = self.analyze_context(post)
            print(f"Context analysis result: {context}")
            
            # Generate response
            print("Generating response...")
            response = self.generate_llm_response(post, context, twin)
            print(f"Generated response: {response}")
            
            return response

        except Exception as e:
            print(f"Error in generate_comment: {str(e)}")
            logger.error(f"Error generating comment for twin {twin.user_profile.username}", exc_info=True)
            return None

    def respond_to_post(self, twin, post):
        """Generate digital twin responses to content"""
        print(f"Responding to content: {post.content[:100]}")
        logger.info(f"""
        Attempting to respond to content:
        Content: {post.content[:100]}
        Post ID: {post.id}
        """)

        responses = []
        try:
            # Generate digital twin response
            logger.info(f"Generating comment using digital twin {twin.user_profile.username}")
            comment_content = self.generate_comment(
                twin=twin, 
                content=post.content,
                post=post
            )
            
            if not comment_content:
                logger.error(f"Failed to generate comment content for digital twin {twin.user_profile.username}")

            if not post.user_profile.is_bot:

                # Create the comment
                comment = Post.objects.create(
                    user_profile=twin.user_profile,
                    # parent_post=post,
                    content=comment_content,
                    experiment=post.experiment
                )
                
                logger.info(f"Created digital twin comment: {comment.content[:50]}...")
                responses.append(comment)

        except Exception as e:
            logger.error(f"Error in twin {twin.user_profile.username} response: {str(e)}", exc_info=True)

        return responses
