import random
import logging
import os
import time
import openai
from typing import Any, Dict, List
from django.conf import settings

from public_discourse_sandbox.pds_app.models import DigitalTwin, Post, Experiment

MAX_ATTEMPTS, MAX_TOKEN_LENGTH, PREVIEW_LENGTH = 3, 512, 250

# Set up logging
logger = logging.getLogger(__name__)

# @receiver(post_save, sender=Post)
# def create_post(sender, instance, created, **kwargs):
#     if created:
#         Post.objects.create(digital_twin=instance)

def validate_config(config):
    assert all(key in config for key in ["AgentCode", "LLM"]), "Both AgentCode and LLM sub-agents are required"
    assert "control_flow" in config["AgentCode"], "AgentCode must have a 'control_flow' key"
    assert all(key in config["LLM"] for key in ["prompt_model", "action_model", "api_key", "functions"]), "LLM is missing required keys"
    return True

class Agent:
    """Main Agent class that orchestrates sub-agents."""
    def __init__(self, sub_agents: Dict[str, Any]):
        self.initialize_agent(sub_agents)
        # self.initialize_memory_modules()
            
    def initialize_agent(self, sub_agents: Dict[str, Any]):
        self.sub_agents = sub_agents
        self.agent_code = AgentCode(sub_agents["AgentCode"])
        self.llm = LLM(sub_agents["LLM"])
        self.working_memory = ""
        self.max_token_length = self.llm.config.get("max_token_length", MAX_TOKEN_LENGTH)
        self.token_counter = 0
        self.status = "BEGIN"

    # def initialize_memory_modules(self):
    #     self.memory_modules = self.sub_agents.get("MemoryModules", [])
    #     for memory_module in self.memory_modules:
    #         get_memory_module(memory_module)
    
    @staticmethod
    def create_output_folder(agent_name: str, timestamp: str) -> str:
        folder_name = f"{agent_name}_{timestamp}"
        folder_path = os.path.join(os.getcwd(), folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        return folder_path

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

    def _ensure_objective(self):
        if self.agent_code is None:
            return  # Skip if agent_code is not set
            
        if self.agent_code.objective not in self.working_memory:
            objective = f"Objective: {self.agent_code.objective}"
            self.working_memory = f"{objective} {self.working_memory}"
            self.token_counter += len(objective.split())

    def execute(self, phase: str, input_data: Any) -> Any:
        """Executes a particular phase using sub-agents."""
        start_time = time.time()
        template = self.agent_code.template(phase, input_data)
        self._add_to_working_memory(template)
        
        output = self.llm.prompt(self.working_memory)
        elapsed_time = time.time() - start_time
        
        return output

    def run(self):
        results = {}
        stage, ct = "BEGIN", 0
        while True:
            ct += 1
            
            if stage == "BEGIN":
                stage = self._begin_stage()  
            elif stage == "ACTION":
                stage_results = self._action_stage()
                stage = self.agent_code.control_flow[stage]
            elif stage == "END":
                return results
            else:
                stage_results = self._execute_stage(stage)
                results[stage] = stage_results[0]
                stage = stage_results[1]

    def _begin_stage(self):
        return self.agent_code.control_flow["BEGIN"]

    def _execute_stage(self, stage):
        output_data = self.execute(stage, self.working_memory)
        if "XXTERMINATEXX" in output_data:
            self.status = "END"
        self.working_memory = output_data
        return (output_data, self.agent_code.control_flow[stage])

    def _action_stage(self):
        action_results = self.llm.act(self.working_memory)
        self._add_to_working_memory(f"{action_results['action']} {action_results['output']}")

class AgentCode:
    def __init__(self, config: Dict[str, Any]):
        if "control_flow" not in config:
            raise ValueError("Missing required key 'control_flow' in config")
        
        self.config = config
        self.objective = config["objective"] if "objective" in config else input("What is my purpose? ")
        self.control_flow = config["control_flow"]
        self.name = config.get("name", "TinyAgent")
    
    def template(self, phase: str, input_data: Any) -> Any:
        if phase not in self.config:
            raise ValueError(f"Undefined phase: {phase}")
        return self.config[phase].format(input_data)


class DTService:
    def __init__(self):
        logger.info("DTListener initialized")
        self.working_memory = ""
        self.token_counter = 0
        self.max_token_length = 512  # Default value, adjust as needed
        self.agent_code = None  # Initialize agent_code as None
    
    def delayed_digital_twin_response(self, post: Post):
        """Function to handle delayed digital twin responses with sequential timing:
        - First twin: 10 seconds after tweet
        - Second twin: 30 seconds after first twin (40s total)
        - Third twin: 10 seconds after second twin (50s total)
        """
        try:

            # First twin response after 10 seconds
            # time.sleep(10)
            first_response = self.respond_to_content(
                post.content,
                post,
                parent_comment=None,
                num_responses=1
            )
            logger.info(f"Generated first digital twin response to post {post.id}")

            # # Second twin response after 30 more seconds
            # # time.sleep(30)
            # second_response = self.respond_to_content(
            #     post.content,
            #     post,
            #     parent_comment=None,
            #     num_responses=1
            # )
            # logger.info(f"Generated second digital twin response to post {post.id}")

            # # Third twin response after 10 more seconds
            # # time.sleep(10)
            # third_response = self.respond_to_content(
            #     post.content,
            #     post,
            #     parent_comment=None,
            #     num_responses=1
            # )
            # logger.info(f"Generated third digital twin response to post {post.id}")

        except Exception as e:
            logger.error(f"Error in delayed digital twin response for post {post.id}: {str(e)}", exc_info=True)

    def get_random_digitial_twins(self, count=1, exclude_twin=None):
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

    def _ensure_objective(self):
        if self.agent_code is None:
            return  # Skip if agent_code is not set
            
        if self.agent_code.objective not in self.working_memory:
            objective = f"Objective: {self.agent_code.objective}"
            self.working_memory = f"{objective} {self.working_memory}"
            self.token_counter += len(objective.split())

    def execute(self, template: str) -> Any:
        """Executes a particular phase using sub-agents."""
        start_time = time.time()
        # template = self.agent_code.template(phase, input_data)
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
        """Analyze the context of a tweet"""
        print(f"Analyzing context for tweet: {post.id}")
        try:
            # Create a simpler context without API calls first
            context = {
                'tweet_content': post.content,
                'tweet_id': post.id,
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
                "ANALYZE": "Analyze this tweet: {0}",
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
        if phase not in self.get_twin_config(twin)["AgentCode"]:
            raise ValueError(f"Undefined phase: {phase}")
        return self.get_twin_config(twin)["AgentCode"][phase].format(input_data)

    def generate_response(self, post: Post, context: Dict = None, twin: DigitalTwin = None) -> str:
        """Generate a response to a tweet"""
        print(f"Generating response for tweet: {post.id}")
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
                    config = {
                        "AgentCode": {
                            "name": twin.user_profile.username,
                            "objective": f"You are {twin.user_profile.username}. {twin.persona}",
                            "control_flow": {
                                "BEGIN": "ANALYZE",
                                "ANALYZE": "RESPOND",
                                "RESPOND": "END"
                            },
                            "ANALYZE": "Analyze this tweet: {0}",
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
                    # template = self.agent_code.template("RESPOND", prompt)
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
        try:
            print(f"\nGenerating comment for digital twin {twin.user_profile.username} on post: {post.id}")
            print(f"Post content: {content}")
            print(f"Digital twin persona: {twin.persona[:100]}...")  # Print first 100 chars of persona
            
            # # Get twin's agent
            # agent = self.get_agent(twin)
            # print("Got twin agent")
            config = {
                "AgentCode": {
                    "name": twin.user_profile.username,
                    "objective": f"You are {twin.user_profile.username}. {twin.persona}",
                    "control_flow": {
                        "BEGIN": "ANALYZE",
                        "ANALYZE": "RESPOND",
                        "RESPOND": "END"
                    },
                    "ANALYZE": "Analyze this tweet: {0}",
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
            
            # Analyze context
            print("Analyzing context...")
            context = self.analyze_context(post)
            print(f"Context analysis result: {context}")
            
            # Generate response
            print("Generating response...")
            response = self.generate_response(post, context, twin)
            print(f"Generated response: {response}")
            
            # Log activity
            # logger.log_activity(
            #     twin_name=twin.user_profile.username,
            #     activity_type='generated_response',
            #     content=content,
            #     response=response,
            #     metadata={'context': context}
            # )
            print("Activity logged")
            
            return response

        except Exception as e:
            print(f"Error in generate_comment: {str(e)}")
            logger.error(f"Error generating comment for twin {twin.user_profile.username}", exc_info=True)
            # logger.log_activity(
            #     twin_name=twin.user_profile.username,
            #     activity_type='error',
            #     content=content,
            #     metadata={'error': str(e)}
            # )
            return None

    def respond_to_content(self, content, post, parent_comment=None, num_responses=2):
        """Generate digital twin responses to content"""
        logger.info(f"""
        Attempting to respond to content:
        Content: {content[:100]}
        Post ID: {post.id}
        Parent Comment: {parent_comment.id if parent_comment else 'None'}
        Number of responses: {num_responses}
        """)

        # Get random digital twins for responses
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

                # Generate digital twin response
                logger.info(f"Generating comment using digital twin {twin.user_profile.username}")
                comment_content = self.generate_comment(
                    twin=twin, 
                    content=content,
                    post=post
                )
                
                if not comment_content:
                    logger.error(f"Failed to generate comment content for digital twin {twin.user_profile.username}")
                    continue

                if not post.user_profile.is_bot:

                    # get default experiment
                    experiment = Experiment.objects.get(name="First")

                    # Create the comment
                    comment = Post.objects.create(
                        user_profile=twin.user_profile,
                        # parent_post=post,
                        content=comment_content,
                        experiment=experiment
                    )

                    print("#########################")
                    
                    logger.info(f"Created digital twin comment: {comment.content[:50]}...")
                    responses.append(comment)

            except Exception as e:
                logger.error(f"Error in twin {twin.user_profile.username} response: {str(e)}", exc_info=True)

        return responses
