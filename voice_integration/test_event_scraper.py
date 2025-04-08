#!/usr/bin/env python3
"""
Test script for the updated EventScraper that uses Firecrawl and Gemini
"""

import asyncio
import json
import logging
from event_scraper import EventScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_event_scraper")

async def test_scraper():
    """Test the EventScraper with sample keywords and location"""
    
    # Initialize the scraper
    scraper = EventScraper()
    
    # Test keywords
    keywords = ["tech", "startup", "AI", "innovation", "networking"]
    location = "San Francisco"
    
    logger.info(f"Testing EventScraper with keywords: {keywords} and location: {location}")
    
    # Search for events
    events = await scraper.search_events(keywords, location)
    
    # Print results
    logger.info(f"Found {len(events)} events")
    print(json.dumps(events, indent=2))
    
    return events

if __name__ == "__main__":
    asyncio.run(test_scraper())
