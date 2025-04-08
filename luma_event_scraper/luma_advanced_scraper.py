#!/usr/bin/env python3
"""
Luma Event Advanced Scraper

This script uses Firecrawl's V1 API to effectively scrape events from Luma,
focusing on SF Bay Area events.
"""

import os
import csv
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
import requests
import time
import pickle

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('luma_advanced_scraper')

# Constants
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"
OUTPUT_FILE = "luma_bay_area_events.csv"
CURRENT_DATE = datetime.now()
MAX_PAGES = 500  # Maximum number of pages to scrape
BATCH_SIZE = 5   # Number of URLs to process in a batch

# SF Bay Area location keywords
BAY_AREA_KEYWORDS = [
    'san francisco', 'sf', 'bay area', 'oakland', 'berkeley', 'palo alto', 
    'san jose', 'mountain view', 'menlo park', 'redwood city', 'sunnyvale',
    'santa clara', 'cupertino', 'san mateo', 'south san francisco', 'daly city',
    'marin', 'sausalito', 'mill valley', 'tiburon', 'larkspur', 'corte madera',
    'novato', 'san rafael', 'richmond', 'el cerrito', 'albany', 'emeryville',
    'alameda', 'hayward', 'fremont', 'milpitas', 'east bay', 'south bay',
    'peninsula', 'silicon valley', 'santa cruz', 'california', 'ca'
]

class LumaAdvancedScraper:
    """Advanced scraper for Luma events using Firecrawl's full capabilities"""
    
    def __init__(self, api_key: str):
        """Initialize the scraper with the Firecrawl API key"""
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.event_urls = set()  # Use a set to avoid duplicates
        self.events = []
        # File to store scraped URLs
        self.scraped_urls_file = 'scraped_urls.pkl'
        self.scraped_urls = self._load_scraped_urls()
    
    def _load_scraped_urls(self) -> set:
        """Load previously scraped URLs from file"""
        if os.path.exists(self.scraped_urls_file):
            try:
                with open(self.scraped_urls_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Error loading scraped URLs: {e}")
                return set()
        return set()
    
    def _save_scraped_urls(self):
        """Save scraped URLs to file"""
        try:
            with open(self.scraped_urls_file, 'wb') as f:
                pickle.dump(self.scraped_urls, f)
        except Exception as e:
            logger.warning(f"Error saving scraped URLs: {e}")
    
    async def scrape_luma_events_page(self, url: str = "https://lu.ma/sf") -> List[Dict[str, Any]]:
        """
        Scrape events from a Luma events page
        
        Args:
            url: URL of the Luma events page
            
        Returns:
            List of event data dictionaries
        """
        logger.info("Starting scrape of Luma events page")
        
        try:
            # Get event URLs
            event_urls = await self.get_event_urls(url)
            logger.info(f"Found {len(event_urls)} event URLs")
            
            # Filter out already scraped URLs
            new_urls = [url for url in event_urls if url not in self.scraped_urls]
            logger.info(f"Found {len(new_urls)} new event URLs to scrape")
            
            # Limit to MAX_PAGES
            if len(new_urls) > MAX_PAGES:
                logger.info(f"Limiting to {MAX_PAGES} events")
                new_urls = new_urls[:MAX_PAGES]
            
            # Process event URLs in batches
            events = []
            total_processed = 0
            
            for i in range(0, len(new_urls), BATCH_SIZE):
                batch_urls = new_urls[i:i+BATCH_SIZE]
                batch_tasks = [self.get_event_details(url) for url in batch_urls]
                batch_results = await asyncio.gather(*batch_tasks)
                
                for j, result in enumerate(batch_results):
                    if result:
                        events.append(result)
                        # Mark URL as scraped
                        self.scraped_urls.add(batch_urls[j])
                        total_processed += 1
                
                logger.info(f"Processed {total_processed}/{len(new_urls)} events")
                
                # Add a small delay between batches to avoid rate limits
                await asyncio.sleep(2)
                
                # Save progress after each batch
                self._save_scraped_urls()
            
            # Save the final set of scraped URLs
            self._save_scraped_urls()
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to scrape events page: {e}")
            return []
    
    async def get_event_urls(self, url: str) -> List[str]:
        """
        Get event URLs from a Luma events page
        
        Args:
            url: URL of the Luma events page
            
        Returns:
            List of event URLs
        """
        logger.info(f"Getting event URLs from {url}")
        
        try:
            # Use the scrape endpoint with browser actions to get event URLs
            payload = {
                "url": url,
                "formats": ["html"],
                "actions": [
                    # Wait for initial page load
                    {"type": "wait", "milliseconds": 3000},
                    # Scroll down multiple times to load more events
                    {"type": "scroll", "distance": 500},
                    {"type": "wait", "milliseconds": 500},
                    {"type": "scroll", "distance": 500},
                    {"type": "wait", "milliseconds": 500}
                ]
            }
            
            logger.info("Starting scrape of Luma events page")
            response = requests.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to scrape events page: {response.status_code} - {response.text}")
                return []
                
            response_data = response.json()
            
            if not response_data.get('success'):
                logger.error(f"Failed to scrape events page: {response_data.get('error')}")
                return []
            
            # Get the HTML content
            html_content = response_data.get('data', {}).get('html', '')
            
            if not html_content:
                logger.error("No HTML content returned for URL " + url)
                return []
            
            # Extract URLs using regex first (more reliable for Luma's site structure)
            logger.info("Extracting event URLs using regex")
            event_urls = re.findall(r'(https://lu\.ma/[a-zA-Z0-9]+)', html_content)
            # Filter out URLs containing '/sf/'
            event_urls = [url for url in event_urls if '/sf/' not in url]
            
            # Deduplicate URLs
            event_urls = list(set(event_urls))
            
            logger.info(f"Found {len(event_urls)} event URLs")
            
            return event_urls
            
        except Exception as e:
            logger.error(f"Error getting event URLs: {str(e)}")
            return []
    
    async def get_event_details(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get event details using the scrape endpoint with the json format
        """
        logger.info(f"Getting details for event: {url}")
        
        try:
            # Use the scrape endpoint with json format to extract structured data
            payload = {
                "url": url,
                "formats": ["json", "markdown"],
                "jsonOptions": {
                    "prompt": """
                    Extract detailed information about this Luma event:
                    - event_name: The title of the event
                    - event_summary: A brief summary of the event
                    - event_date: The date exactly as shown on the page (do not reformat)
                    - event_time: The time exactly as shown on the page
                    - event_location: The location of the event (be specific about city, state, or if it's online)
                    - host_name: The name of the event host or organization
                    - speakers: A list of speakers with the following fields for each:
                      - name: The full name of the speaker
                      - company: The company or organization the speaker is affiliated with
                      - title: The job title or role of the speaker
                    - speaker_details: Extract any additional information about speakers including biographical information that might be present in the event description or dedicated speaker sections
                    
                    Extract ONLY what is explicitly shown on the page - do not make up or infer information.
                    If information is not available, use "Not specified" as the value.
                    For speakers, if there are no speakers clearly listed, return an empty array.
                    """
                }
            }
            
            response = requests.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get event details: {response.status_code} - {response.text}")
                return None
                
            response_data = response.json()
            
            if not response_data.get('success'):
                logger.error(f"Failed to get event details: {response_data.get('error')}")
                return None
            
            # Get the extracted data
            event_data = response_data.get('data', {}).get('json', {})
            
            # Get the full markdown content as event_detail
            event_detail = response_data.get('data', {}).get('markdown', '')
            
            # Add the URL and event_detail to the event data
            event_data['event_url'] = url
            event_data['event_detail'] = event_detail
            
            # Validate the extracted data
            if not self.validate_event_data(event_data):
                logger.warning(f"Skipping event with invalid data: {url}")
                return None
                
            # Mark URL as scraped
            self.scraped_urls.add(url)
            
            return event_data
            
        except Exception as e:
            logger.error(f"Error getting event details: {str(e)}")
            return None
            
    def validate_event_data(self, event_data: Dict[str, Any]) -> bool:
        """
        Validate event data to ensure we have minimum required fields
        """
        # Check if we have event name
        if not event_data.get('event_name') or event_data.get('event_name') == 'Not specified':
            return False
            
        # Check if we have location
        if not event_data.get('event_location') or event_data.get('event_location') == 'Not specified':
            return False
            
        return True
    
    def is_sf_bay_area_location(self, location: str) -> bool:
        """Check if a location is in the SF Bay Area"""
        if not location or location == 'Not specified':
            return False
            
        location_lower = location.lower()
        
        # Check for online/virtual events
        if any(keyword in location_lower for keyword in ['online', 'virtual', 'zoom', 'remote']):
            return False
            
        # Check for Bay Area keywords
        for keyword in BAY_AREA_KEYWORDS:
            if keyword in location_lower:
                return True
                
        return False
    
    def is_future_event(self, date_str: str) -> bool:
        """Check if an event is in the future based on extracted date string"""
        if not date_str or date_str == 'Not specified':
            return False
            
        # Convert months to numbers for pattern matching
        month_to_num = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
            'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
            'january': '01', 'february': '02', 'march': '03', 'april': '04', 'may': '05', 'june': '06',
            'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        
        try:
            # Normalize the date string
            date_lower = date_str.lower()
            
            # Handle common date formats by extracting month and day
            # Look for patterns like "April 11" or "Apr 11, 2025" or "11 April"
            month_day_pattern = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[,\s]+(\d{1,2})', date_lower, re.IGNORECASE)
            
            if month_day_pattern:
                month = month_day_pattern.group(1).lower()
                day = month_day_pattern.group(2).zfill(2)  # Pad single digits with leading zero
                month_num = month_to_num.get(month)
                year = str(CURRENT_DATE.year)
                
                # Check for explicit year in the string
                year_pattern = re.search(r'\b(20\d{2})\b', date_lower)
                if year_pattern:
                    year = year_pattern.group(1)
                
                # Construct date in YYYY-MM-DD format
                constructed_date = f"{year}-{month_num}-{day}"
                
                try:
                    event_date = datetime.strptime(constructed_date, '%Y-%m-%d')
                    
                    # If the date is in the past and no year was specified,
                    # assume it's next year
                    if event_date.date() < CURRENT_DATE.date() and not year_pattern:
                        next_year = str(CURRENT_DATE.year + 1)
                        constructed_date = f"{next_year}-{month_num}-{day}"
                        event_date = datetime.strptime(constructed_date, '%Y-%m-%d')
                    
                    logger.info(f"Parsed date '{date_str}' as '{event_date.date()}'")
                    return event_date.date() >= CURRENT_DATE.date()
                except ValueError:
                    logger.warning(f"Failed to parse constructed date: {constructed_date}")
            
            # Handle standard date formats directly
            for date_format in ['%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y', '%m/%d/%Y', '%m/%d/%y']:
                try:
                    event_date = datetime.strptime(date_str, date_format)
                    return event_date.date() >= CURRENT_DATE.date()
                except ValueError:
                    continue
            
            # If we can't parse it, just return True to include it
            # Better to include some events that might be past than to exclude future ones
            logger.warning(f"Could not determine if date is in future: {date_str}. Including it.")
            return True
            
        except Exception as e:
            logger.warning(f"Error processing date '{date_str}': {str(e)}. Including it.")
            return True
    
    def process_event_data(self, event_data: Dict[str, Any], url: str) -> List[Dict[str, Any]]:
        """Process event data into a format suitable for CSV output"""
        processed_events = []
        
        # Extract basic event information
        event_name = event_data.get('event_name', 'Not specified')
        event_summary = event_data.get('event_summary', 'Not specified')
        event_date = event_data.get('event_date', 'Not specified')
        event_time = event_data.get('event_time', 'Not specified')
        event_location = event_data.get('event_location', 'Not specified')
        host_name = event_data.get('host_name', 'Not specified')
        event_detail = event_data.get('event_detail', '')
        speaker_details = event_data.get('speaker_details', 'Not specified')
        
        # Process speakers
        speakers = event_data.get('speakers', [])
        
        if speakers and len(speakers) > 0:
            # Create a row for each speaker
            for speaker in speakers:
                processed_events.append({
                    "event_name": event_name,
                    "event_summary": event_summary,
                    "event_date": event_date,
                    "event_time": event_time,
                    "event_location": event_location,
                    "event_url": url,
                    "host_name": host_name,
                    "speaker_name": speaker.get('name', 'Not specified'),
                    "speaker_company": speaker.get('company', 'Not specified'),
                    "speaker_title": speaker.get('title', 'Not specified'),
                    "speaker_details": speaker_details,
                    "event_detail": event_detail
                })
        else:
            # Create a row with no speaker
            processed_events.append({
                "event_name": event_name,
                "event_summary": event_summary,
                "event_date": event_date,
                "event_time": event_time,
                "event_location": event_location,
                "event_url": url,
                "host_name": host_name,
                "speaker_name": "Not specified",
                "speaker_company": "Not specified",
                "speaker_title": "Not specified",
                "speaker_details": speaker_details,
                "event_detail": event_detail
            })
            
        return processed_events
    
    def filter_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter events to only include future SF Bay Area events"""
        filtered_events = []
        
        for event in events:
            event_name = event.get('event_name', 'Not specified')
            event_location = event.get('event_location', 'Not specified')
            event_date = event.get('event_date', 'Not specified')
            
            # Check if event is in the SF Bay Area
            is_bay_area = self.is_sf_bay_area_location(event_location)
            
            # Check if event is in the future
            is_future = self.is_future_event(event_date)
            
            if is_bay_area and is_future:
                filtered_events.append(event)
                logger.info(f"Keeping event: {event_name} at {event_location} on {event_date}")
            else:
                if not is_bay_area:
                    logger.info(f"Filtering out non-Bay Area event: {event_name} at {event_location}")
                if not is_future:
                    logger.info(f"Filtering out past event: {event_name} on {event_date}")
        
        return filtered_events
    
    def save_events_to_csv(self, events: List[Dict[str, Any]], filename: str) -> None:
        """Save events to a CSV file"""
        if not events:
            logger.warning("No events to save")
            return
            
        # Check if file exists to determine if we need to write headers
        file_exists = os.path.isfile(filename)
        
        # Define fieldnames
        fieldnames = [
            'event_name', 'event_summary', 'event_date', 'event_time', 
            'event_location', 'event_url', 'host_name', 'speaker_name', 
            'speaker_company', 'speaker_title', 'speaker_details', 'event_detail'
        ]
        
        # Open file in append mode if it exists, otherwise write mode
        mode = 'a' if file_exists else 'w'
        
        try:
            with open(filename, mode, newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Only write header if file doesn't exist
                if not file_exists:
                    writer.writeheader()
                    
                # Write rows
                writer.writerows(events)
                
            logger.info(f"Successfully saved events to {filename}")
        except Exception as e:
            logger.error(f"Error saving events to CSV: {e}")

async def main():
    """Main function to run the scraper"""
    logger.info("Starting Luma Advanced Event Scraper")
    
    # Check if Firecrawl API key is available
    if not FIRECRAWL_API_KEY:
        logger.error("Firecrawl API key not found. Please set FIRECRAWL_API_KEY in .env file")
        return
    
    # Initialize scraper
    scraper = LumaAdvancedScraper(FIRECRAWL_API_KEY)
    
    # Scrape events
    events = await scraper.scrape_luma_events_page("https://lu.ma/sf")
    
    # Process event data
    processed_events = []
    for event in events:
        processed_events.extend(scraper.process_event_data(event, event['event_url']))
    
    # Filter events
    filtered_events = scraper.filter_events(processed_events)
    
    # Save events to CSV
    scraper.save_events_to_csv(filtered_events, OUTPUT_FILE)
    
    # Also save all events to a separate file for reference
    scraper.save_events_to_csv(processed_events, "luma_all_events.csv")
    
    logger.info("Luma Advanced Event Scraper completed")

if __name__ == "__main__":
    asyncio.run(main())