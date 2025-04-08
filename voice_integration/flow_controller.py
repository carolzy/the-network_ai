from typing import Dict, List, Optional, Any
import logging
import os
import random
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv
from voice_integration.question_engine import QuestionEngine
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class FlowController:
    """Controls the multi-step B2B sales flow"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = FlowController()
        return cls._instance
    
    def __init__(self):
        """Initialize the flow controller."""
        # Load API keys
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        logger.info(f"Loaded Gemini API key: {self.gemini_api_key[:10] if self.gemini_api_key else 'Not found'}")
        
        # User data
        self.current_product_line = ""
        self.current_sector = ""
        self.current_segment = ""
        self.keywords = []
        self.linkedin_consent = False
        self.zip_code = ""
        self.user_summary = ""  # Added user summary attribute
        
        # Conversation memory
        self.conversation_memory = []
        self.context_summary = ""
        
        # Flow state
        self.steps = [
            'product',
            'market',
            'differentiation',
            'company_size',
            'linkedin',
            'location',
            'complete'
        ]
        
        # Initialize the question engine
        self.question_engine = QuestionEngine()
    
    async def get_next_step(self, current_step):
        """Get the next step in the flow."""
        try:
            current_index = self.steps.index(current_step)
            if current_index < len(self.steps) - 1:
                return self.steps[current_index + 1]
            else:
                return 'complete'
        except ValueError:
            return 'product'  # Default to the first step if current_step is not found
    
    async def get_question(self, step: str, previous_message: str = None) -> str:
        """Get the question for the current step."""
        try:
            # Build context from previous answers
            context = await self.get_context()
            
            # Get the question from the question engine, passing the previous message
            question = await self.question_engine.get_question(step, context, previous_message)
            
            return question
            
        except Exception as e:
            logger.error(f"Error generating question: {str(e)}")
            return f"Could you tell me more about your {step}?"
    
    async def get_follow_up_question(self, step: str, previous_answer: str, follow_up_count: int = 0, suggest_next: bool = False) -> str:
        """Get a follow-up question for the current step."""
        try:
            # Check if we should suggest moving to the next step
            if suggest_next:
                next_step = await self.get_next_step(step)
                next_step_name = {
                    'product': 'your target market',
                    'market': 'what makes your product unique',
                    'differentiation': 'your target company size',
                    'company_size': 'LinkedIn integration',
                    'linkedin': 'your location',
                    'location': 'completing your setup'
                }.get(next_step, 'the next step')
                
                return f"Thanks for that information. Would you like to add anything else or shall we move on to {next_step_name}?"
            
            # Check for signs of user impatience in the previous answer
            impatience_indicators = [
                "next", "move on", "continue", "skip", "enough", "let's go", 
                "proceed", "done", "finished", "complete", "that's it", "that's all"
            ]
            
            if any(indicator in previous_answer.lower() for indicator in impatience_indicators):
                next_step = await self.get_next_step(step)
                next_question = await self.get_question(next_step)
                return f"Let's move on to the next question. {next_question}"
            
            # Use the Gemini API to generate a follow-up question
            if not self.gemini_api_key:
                logger.warning("No Gemini API key found. Using default follow-up questions.")
                return "Can you tell me more about that?"
            
            # Generate a more conversational follow-up question based on the current context
            prompt = f"""
            You are a friendly B2B research assistant helping a user set up their company research preferences.
            
            Current context:
            - Product/Service: {self.current_product_line or 'Not provided yet'}
            - Target Market: {self.current_sector or 'Not provided yet'}
            - Company Size: {self.current_segment or 'Not provided yet'}
            
            Current step: {step}
            User's answer: "{previous_answer}"
            Follow-up count: {follow_up_count + 1}
            
            Generate a brief, friendly follow-up question that helps clarify or expand on their answer.
            Keep it concise (1 sentence max). Do not use technical jargon.
            If this is the second follow-up (count = 1), make it a final clarification before moving on.
            Do not include any thinking process in your response.
            """
            
            follow_up = await self._call_gemini_api(prompt)
            
            return follow_up
                
        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            return "Can you tell me more about that?"
    
    async def store_answer(self, step, answer):
        """Store the user's answer for the current step."""
        logger.info(f"Storing answer for step '{step}': '{answer}'")
        
        if step == 'product':
            self.current_product_line = answer
            logger.info(f"Updated current_product_line: '{self.current_product_line}'")
            # Generate initial keywords based on product
            try:
                prompt = f"""
                You are a B2B sales assistant helping to generate relevant keywords for targeting.
                
                Product/Service: {answer}
                
                Generate 15 highly relevant keywords or short phrases that would be useful for targeting 
                potential customers based on this product information. Focus on industry terms, job roles, 
                and specific needs that would be relevant to this product/service.
                
                Format your response as a simple JSON array of strings. Do not include any explanation, markdown formatting, or additional text.
                Example: ["keyword1", "keyword2", "keyword3"]
                """
                response = await self._call_gemini_api(prompt)
                self.keywords = await self._parse_keywords_response(response)
                logger.info(f"Generated initial keywords from product: {self.keywords}")
            except Exception as e:
                logger.error(f"Error generating initial keywords: {str(e)}")
                # Set default fallback keywords
                self.keywords = ["B2B", "Sales", "Marketing", "Lead Generation"]
                
        elif step == 'market':
            self.current_sector = answer
            logger.info(f"Updated current_sector: '{self.current_sector}'")
            # Update keywords based on product and market
            try:
                prompt = f"""
                You are a B2B sales assistant helping to generate relevant keywords for targeting.
                
                Current context:
                - Product/Service: {self.current_product_line}
                - Target Market: {answer}
                
                Generate 15 highly relevant keywords or short phrases that would be useful for targeting 
                potential customers based on this information. Focus on industry terms, job roles, 
                and specific needs that would be relevant to this product/service in this market.
                
                Format your response as a simple JSON array of strings. Do not include any explanation, markdown formatting, or additional text.
                Example: ["keyword1", "keyword2", "keyword3"]
                """
                response = await self._call_gemini_api(prompt)
                new_keywords = await self._parse_keywords_response(response)
                # Merge and deduplicate keywords
                self.keywords = list(set(self.keywords + new_keywords))
                logger.info(f"Updated keywords with market info: {self.keywords}")
            except Exception as e:
                logger.error(f"Error updating keywords with market info: {str(e)}")
                
        elif step == 'differentiation':
            # Add to conversation memory for differentiation
            self.conversation_memory.append({
                'step': step,
                'answer': answer
            })
            logger.info(f"Added differentiation to conversation_memory")
            
            # Update keywords based on product, market, and differentiation
            try:
                context = self._build_context()
                prompt = f"""
                You are a B2B sales assistant helping to generate relevant keywords for targeting.
                
                Current context:
                - Product/Service: {context.get('product', '')}
                - Target Market: {context.get('market', '')}
                - Differentiation: {answer}
                
                Generate 15 highly relevant keywords or short phrases that would be useful for targeting 
                potential customers based on this information. Focus on industry terms, job roles, 
                and specific needs that would be relevant to this product/service with this differentiation.
                
                Format your response as a simple JSON array of strings. Do not include any explanation, markdown formatting, or additional text.
                Example: ["keyword1", "keyword2", "keyword3"]
                """
                response = await self._call_gemini_api(prompt)
                new_keywords = await self._parse_keywords_response(response)
                # Merge and deduplicate keywords
                self.keywords = list(set(self.keywords + new_keywords))
                logger.info(f"Updated keywords with differentiation info: {self.keywords}")
            except Exception as e:
                logger.error(f"Error updating keywords with differentiation info: {str(e)}")
            
        elif step == 'company_size':
            self.current_segment = answer
            logger.info(f"Updated current_segment: '{self.current_segment}'")
            
            # Update keywords based on all information
            try:
                context = self._build_context()
                prompt = f"""
                You are a B2B sales assistant helping to generate relevant keywords for targeting.
                
                Current context:
                - Product/Service: {context.get('product', '')}
                - Target Market: {context.get('market', '')}
                - Differentiation: {context.get('differentiation', '')}
                - Company Size: {answer}
                
                Generate 15 highly relevant keywords or short phrases that would be useful for targeting 
                potential customers based on this information. Focus on industry terms, job roles, 
                and specific needs that would be relevant to this product/service for this company size.
                
                Format your response as a simple JSON array of strings. Do not include any explanation, markdown formatting, or additional text.
                Example: ["keyword1", "keyword2", "keyword3"]
                """
                response = await self._call_gemini_api(prompt)
                new_keywords = await self._parse_keywords_response(response)
                # Merge and deduplicate keywords
                self.keywords = list(set(self.keywords + new_keywords))
                logger.info(f"Updated keywords with company size info: {self.keywords}")
            except Exception as e:
                logger.error(f"Error updating keywords with company size info: {str(e)}")
            
        elif step == 'linkedin':
            self.linkedin_consent = answer.lower() in ['yes', 'y', 'true', 'sure', 'ok', 'okay']
            logger.info(f"Updated linkedin_consent: {self.linkedin_consent}")
        elif step == 'location':
            self.zip_code = answer
            logger.info(f"Updated zip_code: '{self.zip_code}'")
        
        # Add to conversation memory if not already added
        if step != 'differentiation':  # We already added differentiation above
            self.conversation_memory.append({
                'step': step,
                'answer': answer
            })
            logger.info(f"Added to conversation_memory, current memory: {self.conversation_memory}")
    
    async def process_answer(self, step: str, answer: str) -> Dict[str, Any]:
        """Process the user's answer for the current step."""
        try:
            # Store the answer
            await self.store_answer(step, answer)
            
            # Get the next step
            next_step = await self.get_next_step(step)
            
            # Generate the next question, passing the user's current answer as previous_message
            next_question = await self.get_question(next_step, answer)
            
            # Generate keywords if we have enough context
            keywords = []
            if len(self.conversation_memory) >= 2:  # At least product and market
                keywords = await self.clean_keywords()
            
            # Return the response
            return {
                'current_step': step,
                'next_step': next_step,
                'next_question': next_question,
                'keywords': keywords
            }
            
        except Exception as e:
            logger.error(f"Error processing answer: {str(e)}")
            return {
                'current_step': step,
                'next_step': 'error',
                'next_question': "I'm sorry, there was an error processing your answer. Could you try again?",
                'keywords': []
            }
    
    async def _call_gemini_api(self, prompt):
        """Call the Gemini API with a prompt and return the response."""
        try:
            if not self.gemini_api_key:
                logger.warning("No Gemini API key found. Using fallback default response.")
                # Return a simple JSON-formatted array of default keywords
                return '["B2B", "Sales", "Marketing", "Lead Generation"]'
                
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}",
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": prompt}]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.2,
                            "topP": 0.8,
                            "topK": 40,
                            "maxOutputTokens": 1024
                        }
                    },
                    timeout=10.0  # Increased timeout for more reliable API calls
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            parts = candidate["content"]["parts"]
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"].strip()
                                # Remove markdown code blocks if present
                                if text.startswith("```") and text.endswith("```"):
                                    # Extract content between code blocks
                                    lines = text.split("\n")
                                    if len(lines) > 2:  # At least 3 lines (opening, content, closing)
                                        # Remove first and last lines (```json and ```)
                                        text = "\n".join(lines[1:-1]).strip()
                                return text
                
                logger.error(f"Gemini API error: {response.status_code} {response.text}")
                # Return a fallback value in case of API error
                return '["B2B", "Sales", "Marketing", "Lead Generation"]'
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            logger.error(traceback.format_exc())
            # Return a fallback value in case of exception
            return '["B2B", "Sales", "Marketing", "Technology"]'
    
    async def _parse_keywords_response(self, response):
        """Parse keywords from the API response."""
        try:
            # Log the original response for debugging
            logger.info(f"Original API response: {response}")
            
            # Clean up the response if it contains markdown
            cleaned_response = response.strip()
            if cleaned_response.startswith('```') and '```' in cleaned_response[3:]:
                # Extract content between markdown code blocks
                logger.info("Detected markdown code block, cleaning response")
                cleaned_response = cleaned_response.split('```', 2)[1]
                if '\n' in cleaned_response:
                    cleaned_response = cleaned_response.split('\n', 1)[1]
                cleaned_response = cleaned_response.strip()
                
                # Remove trailing code block marker if present
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3].strip()
            
            logger.info(f"Cleaned response for JSON parsing: {cleaned_response}")
            
            # Try to parse the cleaned response as JSON
            if cleaned_response.startswith("[") and cleaned_response.endswith("]"):
                try:
                    keywords = json.loads(cleaned_response)
                    if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                        logger.info(f"Successfully parsed keywords from JSON: {keywords}")
                        return keywords
                    else:
                        logger.warning(f"Parsed JSON is not a list of strings: {keywords}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}, response: {cleaned_response}")
            
            # If JSON parsing failed, try to extract keywords manually
            logger.info("Using fallback method to extract keywords from text")
            
            # Remove brackets and quotes
            text = response.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
            
            # Split by commas
            keywords = [k.strip() for k in text.split(",") if k.strip()]
            
            if keywords:
                logger.info(f"Extracted keywords using fallback method: {keywords}")
                return keywords
            
            # If all else fails, return default keywords
            logger.warning("Failed to extract keywords, using defaults")
            return ["B2B", "Sales", "Marketing", "Lead Generation"]
            
        except Exception as e:
            logger.error(f"Error parsing keywords: {str(e)}")
            logger.error(traceback.format_exc())
            # Return default keywords in case of any exception
            return ["B2B", "Sales", "Marketing", "Technology", "Solutions"]
    
    async def clean_keywords(self):
        """Clean up keywords and return them."""
        # Remove duplicates and empty strings
        cleaned_keywords = list(set([k.strip() for k in self.keywords if k.strip()]))
        
        # Sort alphabetically
        cleaned_keywords.sort()
        
        # Log the cleaned keywords
        logger.info(f"Cleaned keywords: {cleaned_keywords}")
        
        # If we still have no keywords, provide some defaults
        if not cleaned_keywords:
            logger.warning("No keywords after cleaning, using defaults")
            cleaned_keywords = ["B2B", "Sales", "Marketing", "Lead Generation"]
        
        # Generate user summary after cleaning keywords
        await self.generate_user_summary()
        
        return cleaned_keywords
    
    async def generate_user_summary(self):
        """Generate a concise summary about the user and their product."""
        try:
            # Get the current context
            context = await self.get_context()
            
            # Use the existing question engine instance to generate the summary
            summary = await self.question_engine.generate_user_summary(context)
            
            # Store the summary
            self.user_summary = summary
            
            logger.info(f"Generated user summary: {summary}")
            
            return summary
        except Exception as e:
            logger.error(f"Error generating user summary: {str(e)}")
            self.user_summary = f"This user is building a {self.current_product_line} for {self.current_sector}."
            return self.user_summary
    
    def get_user_summary(self):
        """Get the current user summary."""
        return self.user_summary
    
    async def get_context(self):
        """Build context from previous answers."""
        context = {}
        
        if self.current_product_line:
            context['product'] = self.current_product_line
        
        if self.current_sector:
            context['market'] = self.current_sector
        
        if self.current_segment:
            context['company_size'] = self.current_segment
        
        # Add differentiation from conversation memory if available
        for item in self.conversation_memory:
            if item['step'] == 'differentiation':
                context['differentiation'] = item['answer']
                break
        
        if self.linkedin_consent:
            context['linkedin_consent'] = True
        
        if self.zip_code:
            context['zip_code'] = self.zip_code
        
        return context
    
    async def reset(self):
        """Reset the flow controller."""
        self.current_product_line = ""
        self.current_sector = ""
        self.current_segment = ""
        self.keywords = []
        self.linkedin_consent = False
        self.zip_code = ""
        self.conversation_memory = []
        self.context_summary = ""
        self.user_summary = ""
        
        return True
