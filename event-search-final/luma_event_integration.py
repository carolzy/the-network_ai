#!/usr/bin/env python3
"""
Luma Event Integration Module

This module integrates the Luma event scraper with the Event Search Agent application.
It provides functions to:
1. Scrape events from Luma
2. Filter events based on keywords and location
3. Format events for display in the UI
"""

import os
import csv
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('luma_event_integration')

# Constants
LUMA_EVENTS_FILE = "luma_bay_area_events.csv"
CURRENT_DATE = datetime.now()

class LumaEventIntegration:
    """Integration class for Luma events with Event Search Agent"""

    def __init__(self, events_file: str = LUMA_EVENTS_FILE):
        """Initialize the integration with the events file"""
        self.events_file = events_file
        self.events = []
        self.load_events()

        # Add hardcoded Berkeley VC Summit event if not already in the events
        self.berkeley_event = {
            "event_title": "Berkeley VC and Startup Summit",
            "event_summary": "Join us for the Berkeley VC and Startup Summit, connecting entrepreneurs and investors in the Berkeley ecosystem.",
            "event_date": "2025-04-20",
            "event_time": "1:00 PM - 6:00 PM",
            "event_location": "Berkeley, California",
            "event_url": "https://lu.ma/zdchxx1a",
            "host_company": "Berkeley Startup Network",
            "speaker_name": "Various Speakers",
            "speaker_title": "Entrepreneurs and VCs",
            "speaker_company": "Multiple Companies",
            "speaker_detail": "Not specified"
        }

        # Check if Berkeley event is already in the events
        berkeley_exists = any(event.get('event_url') == self.berkeley_event['event_url'] for event in self.events)
        if not berkeley_exists:
            self.events.append(self.berkeley_event)

    def load_events(self) -> None:
        """Load events from the CSV file"""
        try:
            if not os.path.exists(self.events_file):
                logger.warning(f"Events file not found: {self.events_file}")
                return

            with open(self.events_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.events = list(reader)

            logger.info(f"Loaded {len(self.events)} events from {self.events_file}")
        except Exception as e:
            logger.error(f"Error loading events: {str(e)}")

    def search_events(self, keywords: List[str], location: str = None) -> List[Dict[str, Any]]:
        """
        Search events based on keywords and location

        Args:
            keywords: List of keywords to search for
            location: Optional location filter

        Returns:
            List of matching events with relevance scores
        """
        if not self.events:
            logger.warning("No events available for search")
            return []

        # Convert keywords to lowercase for case-insensitive matching
        keywords_lower = [k.lower() for k in keywords if k]

        if not keywords_lower:
            logger.info("No valid keywords provided, returning all events")
            return self.events

        matching_events = []

        for event in self.events:
            # Skip events with missing required fields
            if not event.get('event_title') or not event.get('event_summary'):
                continue

            # Apply location filter if provided
            if location and not self._location_matches(event.get('event_location', ''), location):
                continue

            # Calculate relevance score based on keyword matches
            event_text = ' '.join([
                event.get('event_title', ''),
                event.get('event_summary', ''),
                event.get('event_location', ''),
                event.get('host_company', ''),
                event.get('speaker_name', ''),
                event.get('speaker_title', ''),
                event.get('speaker_company', ''),
                event.get('speaker_detail', '')
            ]).lower()

            # Count keyword matches
            matches = []
            for keyword in keywords_lower:
                if keyword in event_text:
                    matches.append(keyword)

            # Add event with match information if there are any matches
            if matches:
                event_copy = event.copy()
                event_copy['relevance_score'] = len(matches) / len(keywords_lower)
                event_copy['matching_keywords'] = matches
                matching_events.append(event_copy)

        # Sort by relevance score (highest first)
        matching_events.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        logger.info(f"Found {len(matching_events)} matching events for keywords: {keywords}")
        return matching_events

    def _location_matches(self, event_location: str, filter_location: str) -> bool:
        """Check if event location matches the filter location"""
        if not event_location or not filter_location:
            return True

        event_location_lower = event_location.lower()
        filter_location_lower = filter_location.lower()

        # Check if filter location is contained in event location
        return filter_location_lower in event_location_lower

    def format_events_for_ui(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format events for display in the UI"""
        formatted_events = []

        for event in events:
            formatted_event = {
                "title": event.get('event_title', 'No Title'),
                "date": event.get('event_date', 'No Date'),
                "time": event.get('event_time', 'No Time'),
                "location": event.get('event_location', 'No Location'),
                "description": event.get('event_summary', 'No Description'),
                "url": event.get('event_url', '#'),
                "host": event.get('host_company', 'No Host'),
                "speakers": [{
                    "name": event.get('speaker_name', 'No Speaker'),
                    "title": event.get('speaker_title', ''),
                    "company": event.get('speaker_company', '')
                }]
            }

            # Add matching keywords if available
            if 'matching_keywords' in event:
                formatted_event['matching_keywords'] = event['matching_keywords']
                formatted_event['relevance_score'] = event.get('relevance_score', 0)

            formatted_events.append(formatted_event)

        return formatted_events

# Example usage
if __name__ == "__main__":
    # Initialize the integration
    integration = LumaEventIntegration()

    # Search for events with keywords
    keywords = ["startup", "VC", "funding"]
    matching_events = integration.search_events(keywords)

    # Format events for UI
    formatted_events = integration.format_events_for_ui(matching_events)

    # Print the results
    print(f"Found {len(formatted_events)} matching events:")
    for event in formatted_events:
        print(f"- {event['title']} ({event['date']})")
        if 'matching_keywords' in event:
            print(f"  Matching keywords: {', '.join(event['matching_keywords'])}")
            print(f"  Relevance score: {event['relevance_score']:.2f}")
