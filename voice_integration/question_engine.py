import random
import logging
import re
import os
import requests
import json
from dotenv import load_dotenv
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Any

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class QuestionEngine:
    """Generates dynamic questions for the onboarding flow based on context"""

    def __init__(self):
        """Initialize the QuestionEngine with prompt templates"""
        self.logger = logging.getLogger(__name__)

        # Check if Gemini API key is available
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if self.gemini_api_key:
            self.logger.info("Gemini API key found. Using dynamic LLM-based questions.")
        else:
            self.logger.warning("No Gemini API key found. Will use basic dynamic question generation.")

        # Steps in the onboarding flow
        self.steps = ['product', 'market', 'differentiation', 'company_size', 'linkedin', 'location', 'complete']

        # Centralized prompt templates for all LLM-based generation
        self.prompt_templates = {
            # Question generation prompts
            'question': {
                'product': """
                Generate a friendly, conversational question asking what product or service the user sells.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their product or service. Keep the entire response concise and conversational.
                """,
                'market': """
                The user sells: {product}

                Generate a friendly, conversational question asking what industry or market sector they target.
                Reference their product/service in your question.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their target market. Keep the entire response concise and conversational.
                """,
                'differentiation': """
                The user sells: {product}
                They target the {market} industry.

                Generate a friendly, conversational question asking what makes their product unique compared to competitors.
                Reference their product/service in your question.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their product differentiation. Keep the entire response concise and conversational.
                """,
                'company_size': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}

                Generate a friendly, conversational question asking what size of companies they typically target
                (e.g., SMB, Mid-Market, Enterprise).
                Reference their product/service in your question.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their target company size. Keep the entire response concise and conversational.
                """,
                'linkedin': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}
                Their target company size: {company_size}

                Generate a friendly, conversational question asking if they would like to connect their LinkedIn account
                to improve recommendations. Explain briefly why this would be helpful.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about LinkedIn integration. Keep the entire response concise and conversational.
                """,
                'location': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}
                Their target company size: {company_size}

                Generate a friendly, conversational question asking for their zip code to help find local events.
                Mention that this is optional and they can skip this step.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their location. Keep the entire response concise and conversational.
                """,
                'complete': """
                Generate a friendly, conversational message thanking the user for providing all the information.
                Let them know that you've gathered everything needed to find great companies for them.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then provide the completion message. Keep the entire response concise and conversational.
                """,
                'default': """
                Generate a friendly, conversational question for the step: {step}
                Context: {context}
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask your question. Keep the entire response concise and conversational.
                """
            },
            # Keyword generation prompt
            'keywords': """
            Based on the following context about a business and its product/service:
            {context}

            Generate keywords that describe the product offering and target customer.
            Generate only the most relevant keywords that would help find ideal target companies.
            Format your response as a comma-separated list of keywords only, without any additional text or explanations.
            Limit to 15 keywords maximum.
            """,
            # Summary generation prompt
            'summary': """
            Based on the following context about a business and its product/service:
            {context}
            
            Generate an insightful, detailed paragraph that summarizes who the user is and what their product does.
            The summary should clearly state what the product/service is, who it's for, and what makes it unique.
            Include specific details about their target market, differentiators, and ideal customer profile.
            
            Format your response as a cohesive paragraph without any additional text or explanations.
            """
        }

        # Load workflow patterns if available
        self.patterns_path = Path("workflows/patterns_v1.json")
        self.workflow_patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[str, Any]:
        """Load workflow patterns from JSON file."""
        try:
            if self.patterns_path.exists():
                with open(self.patterns_path) as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load workflow patterns: {str(e)}")
            return {}

    async def get_question(self, step, context=None, previous_message=None):
        """
        Generate a question based on the current step and context

        Args:
            step (str): The current step in the onboarding flow
            context (dict): Context from previous answers
            previous_message (str): The user's previous message, to check if it contains a question

        Returns:
            str: A dynamically generated question
        """
        if context is None:
            context = {}

        if step is None or step == 'complete':
            step = 'complete'

        # Try to use the LLM first if we have an API key
        if self.gemini_api_key:
            try:
                llm_response = await self._generate_with_llm(step, context, previous_message)
                if llm_response:
                    return llm_response
            except Exception as e:
                logger.error(f"Error using LLM for question generation: {str(e)}")
                # Fall through to basic question generation if LLM fails

        # Generate a basic question if LLM fails or is not available
        return self._generate_basic_question(step, context)

    async def _generate_with_llm(self, step, context, previous_message=None):
        """Generate a question using the Gemini API"""
        try:
            # Construct a prompt based on the current step and context
            prompt = self._construct_prompt(step, context, previous_message)

            # Call the Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    timeout=5.0
                )

            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]
                    if "parts" in content and len(content["parts"]) > 0:
                        question = content["parts"][0]["text"]

                        # Clean up the response to ensure it's a single question
                        question = self._clean_llm_response(question)

                        logger.info(f"Generated question with Gemini API: {question}")
                        return question

                logger.error(f"Unexpected response format from Gemini API: {result}")
                return self._generate_basic_question(step, context)
            else:
                logger.error(f"Error calling Gemini API: {response.status_code} - {response.text}")
                # Fall back to basic question generation
                return self._generate_basic_question(step, context)

        except Exception as e:
            logger.error(f"Error generating question with LLM: {str(e)}")
            # Fall back to basic question generation
            return self._generate_basic_question(step, context)

    def _construct_prompt(self, step, context, previous_message=None):
        """Construct a prompt for the LLM based on the current step and context"""
        # Get the appropriate prompt template for the step
        if step in self.prompt_templates['question']:
            prompt_template = self.prompt_templates['question'][step]
        else:
            prompt_template = self.prompt_templates['question']['default']

        # Add the previous message to the context if provided
        previous_message_context = ""
        if previous_message:
            previous_message_context = f"\nUser's previous message: \"{previous_message}\"\n"

        # Format the prompt with context values
        formatted_prompt = prompt_template.format(
            step=step,
            context=context,
            product=context.get('product', ''),
            market=context.get('market', ''),
            differentiation=context.get('differentiation', ''),
            company_size=context.get('company_size', '')
        )

        # Insert the previous message context after the first line
        if previous_message_context:
            lines = formatted_prompt.split('\n', 1)
            if len(lines) > 1:
                formatted_prompt = lines[0] + previous_message_context + lines[1]
            else:
                formatted_prompt = formatted_prompt + previous_message_context

        return formatted_prompt

    def _clean_llm_response(self, response):
        """Clean up the LLM response to ensure it's a single question"""
        # Remove any "AI:" or "Assistant:" prefixes
        response = re.sub(r'^(AI:|Assistant:)\s*', '', response)

        # Remove any thinking process or explanations in brackets or parentheses
        response = re.sub(r'\[.*?\]|\(.*?\)', '', response)

        # Remove any lines that don't end with a question mark or aren't questions
        lines = response.split('\n')
        question_lines = []
        for line in lines:
            line = line.strip()
            if line and (line.endswith('?') or re.search(r'what|how|why|when|where|which|can|could|would|will|do|does|is|are', line.lower())):
                question_lines.append(line)

        if question_lines:
            return question_lines[0]  # Return the first question

        # If no question was found, return the original response
        return response.strip()

    def _generate_basic_question(self, step, context):
        """Generate a basic question based on the step without using LLM"""
        # Basic questions for each step
        basic_questions = {
            'product': "What product or service does your company offer?",
            'market': "What market or industry are you targeting?",
            'differentiation': "What makes your product unique compared to competitors?",
            'company_size': "What size of companies are you targeting?",
            'linkedin': "Would you like to connect your LinkedIn account to enhance recommendations?",
            'location': "What's your zip code for finding local events? (You can skip this)",
            'complete': "Thanks for providing all the information! We'll find great companies for you."
        }

        # Add context to make the question more personalized
        if step == 'market' and 'product' in context:
            return f"What market or industry are you targeting with your {context['product']}?"
        elif step == 'differentiation' and 'product' in context:
            return f"What makes your {context['product']} unique compared to competitors?"
        elif step == 'company_size' and 'product' in context:
            return f"What size of companies are you targeting with your {context['product']}?"

        # Return the basic question or a generic one if step not found
        return basic_questions.get(step, "Tell me more about your needs.")

    def get_next_step(self, current_step):
        """
        Determine the next step based on the current step

        Args:
            current_step (str): The current step in the onboarding flow

        Returns:
            str: The next step in the onboarding flow
        """
        try:
            current_index = self.steps.index(current_step)
            if current_index < len(self.steps) - 1:
                return self.steps[current_index + 1]
            else:
                return 'complete'
        except ValueError:
            return 'product'  # Default to the first step if current_step is not found

    async def generate_keywords(self, context):
        """
        Generate keywords based on user input

        Args:
            context (dict): Context from previous answers

        Returns:
            list: List of generated keywords
        """
        try:
            # Extract relevant information from context
            product = context.get('product', '')
            market = context.get('market', '')
            differentiation = context.get('differentiation', '')
            company_size = context.get('company_size', '')

            # Combine all information for keyword generation
            combined_context = f"""
            Product/Service: {product}
            Target Market/Industry: {market}
            Unique Value Proposition: {differentiation}
            Target Company Size: {company_size}
            """

            # Use LLM for keyword generation if available
            if self.gemini_api_key:
                keywords = await self._generate_keywords_with_llm(combined_context)
                if keywords:
                    # Optimize the keywords
                    optimized_keywords = self._optimize_keywords(keywords)
                    return optimized_keywords

            # Fallback to basic keyword extraction
            basic_keywords = self._extract_basic_keywords(combined_context)
            return self._optimize_keywords(basic_keywords)

        except Exception as e:
            logger.error(f"Error generating keywords: {str(e)}")
            return ["B2B", "Sales", "Technology", "Innovation"]

    def _optimize_keywords(self, keywords):
        """
        Optimize keywords by deduplicating and ranking by significance

        Args:
            keywords (list): List of keywords to optimize

        Returns:
            list: List of optimized keywords (max 15)
        """
        try:
            # Remove duplicates and empty strings
            unique_keywords = list(set([kw.strip() for kw in keywords if kw.strip()]))

            # Rank keywords by significance
            ranked_keywords = self._rank_keywords_by_significance(unique_keywords)

            # Limit to 15 keywords
            optimized_keywords = ranked_keywords[:15]

            logger.info(f"Optimized keywords: {optimized_keywords}")
            return optimized_keywords
        except Exception as e:
            logger.error(f"Error optimizing keywords: {str(e)}")
            return keywords[:15] if len(keywords) > 15 else keywords

    def _rank_keywords_by_significance(self, keywords):
        """
        Rank keywords by their significance

        Args:
            keywords (list): List of unique keywords

        Returns:
            list: List of keywords ranked by significance
        """
        try:
            # Score each keyword based on multiple factors
            keyword_scores = {}

            for keyword in keywords:
                # Initialize score
                score = 0

                # Factor 1: Length (longer keywords are often more specific)
                # But not too long
                length = len(keyword)
                if 3 <= length <= 20:
                    score += min(length / 5, 3)  # Cap at 3 points

                # Factor 2: Multi-word phrases are more specific
                word_count = len(keyword.split())
                if word_count > 1:
                    score += min(word_count, 3)  # Cap at 3 points

                # Factor 3: Industry-specific terms
                industry_terms = ["b2b", "saas", "enterprise", "platform", "solution",
                                 "technology", "ai", "ml", "data", "analytics", "cloud",
                                 "software", "service", "automation", "integration", "management"]
                if keyword.lower() in industry_terms or any(term in keyword.lower() for term in industry_terms):
                    score += 2

                keyword_scores[keyword] = score

            # Sort keywords by score (descending)
            sorted_words = sorted(keywords, key=lambda k: keyword_scores.get(k, 0), reverse=True)

            return sorted_words
        except Exception as e:
            logger.error(f"Error ranking keywords: {str(e)}")
            return keywords

    async def generate_user_summary(self, context):
        """
        Generate an insightful summary about the user and their product

        Args:
            context (dict): Context from previous answers

        Returns:
            str: An insightful summary sentence
        """
        try:
            # Extract relevant information from context
            product = context.get('product', '')
            market = context.get('market', '')
            differentiation = context.get('differentiation', '')
            company_size = context.get('company_size', '')

            # Combine all information for summary generation
            combined_context = f"""
            Product/Service: {product}
            Target Market/Industry: {market}
            Unique Value Proposition: {differentiation}
            Target Company Size: {company_size}
            """

            # Use LLM for summary generation if available
            if self.gemini_api_key:
                summary = await self._generate_summary_with_llm(combined_context)
                if summary:
                    return summary

            # Fallback to basic summary generation
            return self._generate_basic_summary(context)

        except Exception as e:
            logger.error(f"Error generating user summary: {str(e)}")
            return "This user is building a product for business customers."

    async def _generate_summary_with_llm(self, context):
        """Generate a insightful summary using the Gemini API"""
        try:
            # Prepare the prompt for summary generation using the centralized template
            prompt = self.prompt_templates['summary'].format(context=context)

            # Call the Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    timeout=5.0
                )

            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]
                    if "parts" in content and len(content["parts"]) > 0:
                        summary = content["parts"][0]["text"].strip()

                        # Clean up the summary
                        summary = summary.replace('"', '').strip()

                        logger.info(f"Generated summary with LLM: {summary}")
                        return summary

            logger.error(f"Error or unexpected response from Gemini API")
            return None

        except Exception as e:
            logger.error(f"Error generating summary with LLM: {str(e)}")
            return None

    def _generate_basic_summary(self, context):
        """Generate a basic summary from context"""
        try:
            product = context.get('product', 'a product')
            market = context.get('market', 'businesses')

            summary = f"This user is building {product} for {market}."
            return summary
        except Exception as e:
            logger.error(f"Error generating basic summary: {str(e)}")
            return "This user is building a product for business customers."

    async def _generate_keywords_with_llm(self, context):
        """Generate keywords using the Gemini API"""
        try:
            # Prepare the prompt for keyword generation using the centralized template
            prompt = self.prompt_templates['keywords'].format(context=context)

            # Call the Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    timeout=5.0
                )

            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]
                    if "parts" in content and len(content["parts"]) > 0:
                        keywords_text = content["parts"][0]["text"]

                        # Parse the keywords from the response
                        keywords_list = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]

                        # Limit to 15 keywords
                        keywords_list = keywords_list[:15]

                        logger.info(f"Generated keywords with LLM: {keywords_list}")
                        return keywords_list

            logger.error(f"Error or unexpected response from Gemini API")
            return None

        except Exception as e:
            logger.error(f"Error generating keywords with LLM: {str(e)}")
            return None

    def _extract_basic_keywords(self, text):
        """Extract basic keywords from text using simple rules"""
        # Convert to lowercase and split by common separators
        words = re.findall(r'\b\w+\b', text.lower())

        # Remove common stop words
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'as', 'of', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'that', 'which', 'who', 'whom', 'this', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'does', 'did', 'doing', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]

        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Get the most frequent words as keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, count in sorted_words[:15]]

        # Add some common business keywords if we don't have enough
        if len(keywords) < 5:
            common_keywords = ["B2B", "enterprise", "software", "technology", "solution", "platform", "service", "analytics", "automation", "AI", "cloud", "data", "security", "integration", "management"]
            keywords.extend(common_keywords[:10 - len(keywords)])

        return keywords
