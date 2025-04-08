import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import json
import re
from datetime import datetime, timedelta
import os
import google.generativeai as genai
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
from typing import List, Dict, Any
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Firecrawl
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")
firecrawl_app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

# Initialize Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel('gemini-2.0-flash')

# Current date for validation
CURRENT_DATE = datetime.now()

# Debug mode
DEBUG_MODE = os.environ.get("DEBUG", "True").lower() == "true"

# Recency weight for sorting (how much to prioritize recent events)
RECENCY_WEIGHT = float(os.environ.get("RECENCY_WEIGHT", "0.2"))

class EventScraper:
    """
    Scraper for Luma Events based on keywords and location.
    Adapts browser automation techniques from OpenManus project.
    """
    
    def __init__(self):
        self.base_url = "https://lu.ma/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
    
    async def search_events(self, keywords, location=None, max_results=10):
        """
        Search for events based on keywords and location.
        
        Args:
            keywords (list): List of keywords to search for
            location (str, optional): Location to search in. Defaults to None.
            max_results (int, optional): Maximum number of results to return. Defaults to 10.
            
        Returns:
            list: List of event dictionaries
        """
        # Select the most relevant keywords (max 5)
        search_keywords = self._select_relevant_keywords(keywords, max_keywords=5)
        logger.info(f"Searching for events with keywords: {search_keywords}")
        
        # Combine keywords into a search query
        search_query = " ".join(search_keywords)
        
        # Add location if provided
        if location:
            search_query += f" {location}"
        
        # Encode the search query for URL
        encoded_query = quote_plus(search_query)
        search_url = f"{self.base_url}?q={encoded_query}"
        
        try:
            # Fetch the search results page
            async with httpx.AsyncClient() as client:
                response = await client.get(search_url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                
                # Parse the HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract events
                events = await self._extract_events_from_html(soup, keywords)
                
                # Limit the number of results
                return events[:max_results]
                
        except Exception as e:
            logger.error(f"Error searching for events: {str(e)}")
            return []
    
    def _select_relevant_keywords(self, keywords, max_keywords=5):
        """
        Select the most relevant keywords for the search.
        
        Args:
            keywords (list): List of all keywords
            max_keywords (int, optional): Maximum number of keywords to select. Defaults to 5.
            
        Returns:
            list: List of selected keywords
        """
        # For now, just take the first few keywords
        # In a more sophisticated implementation, we could use TF-IDF or other relevance metrics
        return keywords[:max_keywords]
    
    async def _extract_events_from_html(self, soup, all_keywords):
        """
        Extract events from the HTML soup.
        
        Args:
            soup (BeautifulSoup): BeautifulSoup object of the search results page
            all_keywords (list): List of all keywords to match against event descriptions
            
        Returns:
            list: List of event dictionaries
        """
        events = []
        
        # Determine location code
        location_code = "sf"  # Default to San Francisco
        
        # Step 1: Scrape events from Luma
        events = await self._scrape_events(location_code)
        
        if not events:
            logger.warning("No events found to analyze")
            return []
        
        # Step 2: Analyze relevance of each event
        analyzed_events = []
        for event in events:
            logger.info(f"Processing event: {event.get('event_name')}")
            
            # Analyze relevance
            relevance_result = await self._analyze_event_relevance(event, all_keywords)
            
            # Add relevance data to event
            event['relevance_score'] = relevance_result.get('relevance_score', 0.0)
            event['relevance_highlight'] = relevance_result.get('highlight', 'No highlight available')
            
            analyzed_events.append(event)
        
        # Step 3: Calculate combined scores (relevance + recency)
        for event in analyzed_events:
            event['combined_score'] = self._calculate_combined_score(event)
        
        # Step 4: Sort by combined score (highest first)
        sorted_events = sorted(analyzed_events, key=lambda x: x.get('combined_score', 0.0), reverse=True)
        
        # Step 5: Format events for display
        formatted_events = []
        for event in sorted_events:
            formatted_events.append({
                "title": event.get('event_name', 'Untitled Event'),
                "date": self._format_date(event.get('event_date_time', '')),
                "location": event.get('location', 'Unknown Location'),
                "description": event.get('event_description', 'No description available'),
                "url": event.get('event_url', ''),
                "matchingKeywords": all_keywords,
                "relevanceScore": round(event.get('relevance_score', 0.0) * 100),
                "relevanceHighlight": event.get('relevance_highlight', '')
            })
        
        logger.info(f"Returning top {len(formatted_events)} events")
        return formatted_events
    
    async def _scrape_events(self, location: str = "sf") -> List[Dict[str, Any]]:
        """
        Scrape events from Luma based on location
        Currently supports: sf (San Francisco), nyc (New York)
        """
        logger.info(f"Scraping events from lu.ma/{location}...")
        
        try:
            # Determine URL based on location
            if location.lower() in ["sf", "san francisco"]:
                url = "https://lu.ma/sf"
            elif location.lower() in ["nyc", "new york"]:
                url = "https://lu.ma/nyc"
            else:
                logger.warning(f"Location {location} not supported, defaulting to SF")
                url = "https://lu.ma/sf"
            
            # Use Firecrawl to scrape and extract events
            logger.info(f"Sending request to Firecrawl API for {url}")
            result = firecrawl_app.extract(
                [url],
                {
                    'prompt': f"""
                    Extract all events from this page. For each event include:
                    - event_name: The title of the event
                    - event_description: A description of the event if available
                    - event_url: The URL link to the event
                    - event_date_time: When the event takes place (date and time)
                    - speakers: List of speakers with their name, title, and company if available
                    - registration_link: Link to register for the event
                    
                    IMPORTANT: Only extract events that are happening on or after {CURRENT_DATE.strftime('%Y-%m-%d')}. Do not include past events.
                    """,
                    'schema': {
                        "type": "object",
                        "properties": {
                            "events": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "event_name": {"type": "string"},
                                        "event_description": {"type": "string"},
                                        "event_url": {"type": "string"},
                                        "event_date_time": {"type": "string"},
                                        "speakers": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "title": {"type": "string"},
                                                    "company": {"type": "string"}
                                                },
                                                "required": ["name"]
                                            }
                                        },
                                        "registration_link": {"type": "string"}
                                    },
                                    "required": ["event_name", "event_url", "event_date_time"]
                                }
                            }
                        },
                        "required": ["events"]
                    },
                    'enableWebSearch': True,
                    'debug': DEBUG_MODE
                }
            )
            
            logger.info(f"Received {len(result.get('data', {}).get('events', []))} events from Firecrawl")
            
            if not result.get('success'):
                logger.error(f"Error extracting events: {result.get('error', 'Unknown error')}")
                return []
            
            all_events = result.get('data', {}).get('events', [])
            if not all_events:
                logger.warning("No events found from API")
                return []
                
            # Validate events based on criteria
            valid_events = []
            for event in all_events:
                # Check 1: Valid event URL (must be from lu.ma)
                event_url = event.get('event_url', '')
                if not event_url or not event_url.startswith('https://lu.ma/'):
                    logger.debug(f"Skipping event with invalid URL: {event_url}")
                    continue
                
                # Check 2: If description is empty, use the event name as a fallback
                event_description = event.get('event_description', '').strip()
                if not event_description:
                    event['event_description'] = event.get('event_name', 'No description available')
                    
                # Check 3: Date validation - must be in the future
                event_date_str = event.get('event_date_time', '')
                try:
                    # Handle different date formats
                    if 'T' in event_date_str:
                        # ISO format
                        event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                    else:
                        # Try other common formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                            try:
                                event_date = datetime.strptime(event_date_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            raise ValueError(f"Could not parse date: {event_date_str}")
                    
                    # Only check if event is in the future (no upper limit)
                    if event_date < CURRENT_DATE:
                        logger.debug(f"Skipping past event: {event.get('event_name')} on {event_date_str}")
                        continue
                    
                    # Store the parsed date for recency calculation
                    event['parsed_date'] = event_date
                        
                except Exception as e:
                    logger.warning(f"Error parsing date '{event_date_str}': {str(e)}")
                    continue
                    
                # Add valid event
                valid_events.append(event)
                
            logger.info(f"Found {len(valid_events)} valid events after filtering")
            return valid_events
                
        except Exception as e:
            logger.error(f"Error scraping events: {str(e)}")
            return []
    
    async def _analyze_event_relevance(self, event, keywords: List[str]) -> Dict[str, Any]:
        """
        Analyze the relevance of an event to the provided keywords
        Returns a relevance score and highlight
        """
        event_name = event.get('event_name', '')
        event_description = event.get('event_description', '')
        
        # Extract speaker information
        speakers_info = ""
        speakers = event.get('speakers', [])
        for speaker in speakers:
            name = speaker.get('name', '')
            title = speaker.get('title', '')
            company = speaker.get('company', '')
            speakers_info += f"{name}"
            if title:
                speakers_info += f" ({title}"
                if company:
                    speakers_info += f" at {company}"
                speakers_info += ")"
            speakers_info += ", "
        
        # Prepare event data for analysis
        event_data = f"""
        Event Name: {event_name}
        Description: {event_description}
        Speakers: {speakers_info}
        """
        
        # Prepare prompt for Gemini
        prompt = f"""
        Analyze the relevance of the following event to these keywords: {', '.join(keywords)}
        
        {event_data}
        
        Return a JSON object with:
        1. "relevance_score": A float between 0.0 and 1.0 indicating how relevant this event is to the keywords
        2. "highlight": A brief explanation of why this event is relevant or not relevant
        
        The relevance score should be:
        - 0.0: Not relevant at all
        - 0.3: Slightly relevant (mentions keywords but not a focus)
        - 0.5: Moderately relevant (related to keywords)
        - 0.7: Very relevant (directly addresses keywords)
        - 1.0: Extremely relevant (perfectly matches keywords)
        
        Format your response as a valid JSON object only, with no additional text.
        """
        
        logger.info(f"Analyzing relevance of event: {event_name} to keywords: {keywords}")
        
        try:
            logger.info("Sending request to Gemini for relevance analysis")
            response = gemini.generate_content(prompt)
            
            # Extract JSON from response
            result_text = response.text
            
            # Handle potential formatting issues in the response
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # Try to extract JSON if it's wrapped in markdown code blocks or has extra text
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # Last resort - try to find anything that looks like JSON
                    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        raise ValueError("Could not extract JSON from response")
            
            # Ensure the result has the expected fields
            if 'relevance_score' not in result or 'highlight' not in result:
                logger.warning(f"Incomplete response from Gemini: {result}")
                return {
                    'relevance_score': 0.0,
                    'highlight': "Could not determine relevance (incomplete analysis)"
                }
            
            # Ensure relevance_score is a float between 0 and 1
            relevance_score = float(result['relevance_score'])
            relevance_score = max(0.0, min(1.0, relevance_score))
            
            return {
                'relevance_score': relevance_score,
                'highlight': result['highlight']
            }
            
        except Exception as e:
            logger.error(f"Error analyzing event relevance: {str(e)}")
            return {
                'relevance_score': 0.0,
                'highlight': f"Could not determine relevance (error: {str(e)})"
            }
    
    def _calculate_combined_score(self, event):
        """
        Calculate a combined score based on relevance and recency
        """
        relevance_score = event.get('relevance_score', 0.0)
        
        # Calculate recency score (1.0 for today, decreasing as event gets further away)
        days_until_event = (event.get('parsed_date', CURRENT_DATE) - CURRENT_DATE).days
        # Normalize to a 0-1 scale (closer to 1 means more recent)
        # Use a logarithmic scale to prevent far-future events from getting too low a score
        recency_score = 1.0 / (1.0 + math.log(1 + days_until_event))
        
        # Store the recency score for reference
        event['recency_score'] = recency_score
        
        # Calculate combined score with configurable weight
        # Formula: (1-w) * relevance + w * recency
        combined_score = (1 - RECENCY_WEIGHT) * relevance_score + RECENCY_WEIGHT * recency_score
        
        return combined_score
    
    def _format_date(self, date_str):
        """Format date string for display"""
        try:
            if 'T' in date_str:
                # ISO format
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                # Try other common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return date_str  # Return original if parsing fails
            
            # Format the date nicely
            return dt.strftime('%A, %B %d, %Y at %I:%M %p')
        except Exception:
            return date_str  # Return original if any error occurs

# For testing
async def test_scraper():
    scraper = EventScraper()
    keywords = ["startup", "founder", "networking", "tech", "innovation"]
    events = await scraper.search_events(keywords, "San Francisco")
    print(json.dumps(events, indent=2))

if __name__ == "__main__":
    asyncio.run(test_scraper())
