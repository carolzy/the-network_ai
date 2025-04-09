#!/usr/bin/env python3
"""
Combined Event Search Agent - A streamlined event finder using Gemini
Takes the best features from both event_search_agent versions and uses CSV data
"""

import os
import json
import time
import logging
import asyncio
import csv
import re
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('combined_event_search_agent')

# Load environment variables
load_dotenv()

# Path to the CSV file with events
CSV_FILE_PATH = os.environ.get(
    "CSV_FILE_PATH",
    "./luma_bay_area_events.csv"
)

# Initialize Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
gemini = genai.GenerativeModel('gemini-2.0-flash')

# Current date for validation
CURRENT_DATE = datetime.now()

# Debug mode
DEBUG_MODE = os.environ.get("DEBUG", "True").lower() == "true"

# Version for cache busting
VERSION = str(int(time.time()))

# Recency weight for sorting (how much to prioritize recent events)
RECENCY_WEIGHT = float(os.environ.get("RECENCY_WEIGHT", "0.2"))

def load_events_from_csv(csv_file_path: str = CSV_FILE_PATH) -> List[Dict[str, Any]]:
    """
    Load events from the CSV file

    Args:
        csv_file_path: Path to the CSV file with events

    Returns:
        List of event dictionaries
    """
    logger.info(f"Loading events from CSV file: {csv_file_path}")

    try:
        if not os.path.exists(csv_file_path):
            logger.error(f"CSV file not found: {csv_file_path}")
            return []

        events = []
        event_dict = {}  # Dictionary to store events by URL to handle multiple speakers

        with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # Get the field names from the CSV to handle different column naming
            field_names = reader.fieldnames

            # Map standard field names to possible CSV column names
            field_mapping = {
                'event_name': ['event_name', 'event_title'],
                'event_description': ['event_summary', 'event_detail'],
                'event_date': ['event_date'],
                'event_time': ['event_time'],
                'event_location': ['event_location'],
                'event_url': ['event_url'],
                'host_name': ['host_name', 'host_company'],
                'speaker_name': ['speaker_name'],
                'speaker_title': ['speaker_title'],
                'speaker_company': ['speaker_company'],
                'speaker_details': ['speaker_details', 'speaker_detail']
            }

            # Create a mapping from CSV columns to standard field names
            column_mapping = {}
            for std_field, possible_names in field_mapping.items():
                for name in possible_names:
                    if name in field_names:
                        column_mapping[name] = std_field
                        break

            for row in reader:
                # Map the CSV columns to standard field names
                mapped_row = {}
                for csv_field, value in row.items():
                    if csv_field in column_mapping:
                        mapped_row[column_mapping[csv_field]] = value
                    else:
                        mapped_row[csv_field] = value

                event_url = mapped_row.get('event_url', '')

                # Skip rows with missing essential data
                if not event_url or not mapped_row.get('event_name', ''):
                    continue

                # If this is a new event, create a new entry
                if event_url not in event_dict:
                    # Combine date and time for the event_date_time field
                    event_date = mapped_row.get('event_date', '')
                    event_time = mapped_row.get('event_time', '')
                    event_date_time = f"{event_date} {event_time}".strip()

                    event_dict[event_url] = {
                        'event_name': mapped_row.get('event_name', ''),
                        'event_description': mapped_row.get('event_description', ''),
                        'event_url': event_url,
                        'event_date_time': event_date_time,
                        'event_date': event_date,
                        'event_time': event_time,
                        'event_location': mapped_row.get('event_location', ''),
                        'host_name': mapped_row.get('host_name', ''),
                        'speakers': [],
                        'event_detail': mapped_row.get('event_detail', '')
                    }

                # Add speaker information if available
                speaker_name = mapped_row.get('speaker_name', '')
                if speaker_name and speaker_name != 'Not specified':
                    speaker_info = {
                        'name': speaker_name,
                        'title': mapped_row.get('speaker_title', ''),
                        'company': mapped_row.get('speaker_company', ''),
                        'details': mapped_row.get('speaker_details', '')
                    }
                    # Only add if not already in the list
                    if not any(s.get('name') == speaker_name for s in event_dict[event_url]['speakers']):
                        event_dict[event_url]['speakers'].append(speaker_info)

        # Convert dictionary to list
        events = list(event_dict.values())
        logger.info(f"Loaded {len(events)} events from CSV file")
        return events

    except Exception as e:
        logger.error(f"Error loading events from CSV: {str(e)}")
        return []

def parse_event_date(date_str: str) -> Optional[datetime]:
    """
    Parse event date string into a datetime object using multiple formats

    Args:
        date_str: Date string to parse

    Returns:
        Datetime object or None if parsing fails
    """
    if not date_str or date_str == 'Not specified':
        return None

    # Try various date formats
    date_formats = [
        '%Y-%m-%d',
        '%B %d, %Y',
        '%b %d, %Y',
        '%d %B %Y',
        '%d %b %Y',
        '%m/%d/%Y',
        '%Y/%m/%d'
    ]

    # First try direct parsing
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try to extract month and day using regex
    month_to_num = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    # Match patterns like "April 15" or "15 April"
    patterns = [
        r'(\w+)\s+(\d{1,2})',  # Month Day
        r'(\d{1,2})\s+(\w+)'   # Day Month
    ]

    for pattern in patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            groups = match.groups()

            # Determine which group is month and which is day
            if groups[0].isdigit():  # Day Month
                day = int(groups[0])
                month_str = groups[1].lower()

                if month_str in month_to_num:
                    month = month_to_num[month_str]
                    year = datetime.now().year

                    # Adjust year if date is in the past
                    try:
                        event_date = datetime(year, month, day)
                        if event_date < datetime.now():
                            event_date = datetime(year + 1, month, day)
                        return event_date
                    except ValueError:
                        pass  # Invalid date like February 30
            else:  # Month Day
                month_str = groups[0].lower()

                if month_str in month_to_num:
                    month = month_to_num[month_str]
                    day = int(groups[1])
                    year = datetime.now().year

                    # Adjust year if date is in the past
                    try:
                        event_date = datetime(year, month, day)
                        if event_date < datetime.now():
                            event_date = datetime(year + 1, month, day)
                        return event_date
                    except ValueError:
                        pass  # Invalid date

    # Look for a 4-digit year in the string
    year_match = re.search(r'\b(20\d{2})\b', date_str)
    if year_match:
        year = int(year_match.group(1))
        # Extract month and day if possible
        for month_name, month_num in month_to_num.items():
            if month_name in date_str.lower():
                # Look for a 1-2 digit day
                day_match = re.search(r'\b(\d{1,2})\b', date_str)
                if day_match:
                    try:
                        day = int(day_match.group(1))
                        if 1 <= day <= 31:  # Basic validation
                            return datetime(year, month_num, day)
                    except ValueError:
                        pass  # Invalid date

    return None

def is_future_event(event: Dict[str, Any]) -> bool:
    """
    Determine if an event is in the future

    Args:
        event: Event dictionary

    Returns:
        True if the event is in the future, False otherwise
    """
    event_date_str = event.get('event_date', '')
    event_date_time_str = event.get('event_date_time', '')

    # Try to parse the date
    event_date = parse_event_date(event_date_str or event_date_time_str)

    # If we couldn't parse the date, assume it's a future event
    if not event_date:
        logger.warning(f"Could not parse date for event: {event.get('event_name')}. Assuming future event.")
        return True

    # Store the parsed date for later use
    event['parsed_date'] = event_date

    # Check if the event is in the future
    return event_date.date() >= CURRENT_DATE.date()

def analyze_event_relevance(event: Dict[str, Any], keywords: List[str], user_summary: str = "", debug: bool = False) -> Dict[str, Any]:
    """
    Analyze the relevance of an event to the provided keywords and user summary
    Returns a relevance score and highlight

    Args:
        event: Event dictionary
        keywords: List of keywords to match
        user_summary: User's self-description and interests
        debug: Whether to print debug information

    Returns:
        Dictionary with relevance score and highlight
    """
    event_name = event.get('event_name', '')
    event_description = event.get('event_description', '')
    event_location = event.get('event_location', '')
    event_detail = event.get('event_detail', '')
    host_name = event.get('host_name', '')

    # Extract speaker information
    speakers_info = ""
    speakers = event.get('speakers', [])
    for speaker in speakers:
        name = speaker.get('name', '')
        title = speaker.get('title', '')
        company = speaker.get('company', '')
        details = speaker.get('details', '')

        speakers_info += f"{name}"
        if title:
            speakers_info += f" ({title}"
            if company:
                speakers_info += f" at {company}"
            speakers_info += ")"
        speakers_info += ", "

        if details and details != 'Not specified':
            speakers_info += f"Bio: {details}. "

    # Prepare detailed event data for analysis
    event_data = f"""
    Event Name: {event_name}
    Description: {event_description}
    Location: {event_location}
    Host: {host_name}
    Speakers: {speakers_info}
    Full Details: {event_detail if event_detail else 'No additional details available'}
    """

    # Prepare prompt for Gemini with user summary if available
    user_context = f"User Summary: {user_summary}" if user_summary else "No user summary provided"

    prompt = f"""
    Analyze the relevance of the following event to these keywords: {', '.join(keywords)}

    {event_data}

    {user_context}

    Consider these aspects when determining relevance:
    1. How closely does the event align with the provided keywords?
    2. Is the event focused on topics, industries, or technologies related to the keywords?
    3. Are the speakers or host organization relevant to the keywords?
    4. Would someone interested in {', '.join(keywords)} find this event valuable to attend?
    5. How specific is the connection between the event and the keywords?

    If a user summary is provided, also consider:
    6. How relevant is this event to this specific user's background, interests, and goals?
    7. Are there specific aspects of the event that align with the user's professional or personal interests?
    8. Would this event provide valuable networking opportunities, knowledge, or experiences for this user?

    Return a JSON object with:
    1. "relevance_score": A float between 0.0 and 1.0 indicating how relevant this event is to the keywords and user
    2. "highlight": A detailed explanation that:
       - Highlights specific reasons why this event would be valuable for someone interested in the keywords
       - If user summary is provided, explains why this user specifically would find this event valuable
       - Mentions specific speakers, topics, or networking opportunities that match the user's interests
       - Points out unique aspects of this event that align with the user's background or goals

    The relevance score should be:
    - 0.0: Not relevant at all
    - 0.3: Slightly relevant (mentions keywords but not a focus)
    - 0.5: Moderately relevant (related to keywords)
    - 0.7: Very relevant (directly addresses keywords)
    - 1.0: Extremely relevant (perfectly matches keywords and user interests)

    Make the highlight informative, specific, and actionable - explain exactly why the user should attend.

    Format your response as a valid JSON object only, with no additional text.
    """

    logger.info(f"Analyzing relevance of event: {event_name} to keywords: {keywords}")

    # Retry logic with exponential backoff
    max_retries = 3
    base_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to Gemini for relevance analysis (attempt {attempt+1}/{max_retries})")
            response = gemini.generate_content(prompt)

            # Extract JSON from response
            result_text = response.text

            # Handle potential formatting issues in the response
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # Try to extract JSON if it's wrapped in markdown code blocks or has extra text
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
            logger.error(f"Error analyzing event relevance (attempt {attempt+1}/{max_retries}): {str(e)}")

            # If we hit a rate limit error, wait and retry
            if "429" in str(e) and attempt < max_retries - 1:
                # Calculate delay with exponential backoff and jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Rate limit hit. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                continue

            # If it's the last attempt or not a rate limit error, return a default response
            if attempt == max_retries - 1:
                # For the last attempt, provide a basic relevance score based on keyword matching
                basic_score = calculate_basic_relevance(event, keywords)
                return {
                    'relevance_score': basic_score,
                    'highlight': f"Based on keyword matching: This event may be relevant to {', '.join(keywords)}."
                }

    # This should not be reached, but just in case
    return {
        'relevance_score': 0.0,
        'highlight': "Could not determine relevance (API error)"
    }

def calculate_basic_relevance(event: Dict[str, Any], keywords: List[str]) -> float:
    """
    Calculate a basic relevance score based on keyword matching when Gemini API is unavailable

    Args:
        event: Event dictionary
        keywords: List of keywords to match

    Returns:
        Relevance score between 0.0 and 0.7
    """
    event_name = event.get('event_name', '').lower()
    event_description = event.get('event_description', '').lower()
    event_location = event.get('event_location', '').lower()
    event_detail = event.get('event_detail', '').lower()
    host_name = event.get('host_name', '').lower()

    # Extract speaker information
    speakers_text = ""
    for speaker in event.get('speakers', []):
        name = speaker.get('name', '').lower()
        title = speaker.get('title', '').lower()
        company = speaker.get('company', '').lower()
        details = speaker.get('details', '').lower()
        speakers_text += f"{name} {title} {company} {details} "

    # Combine all text
    all_text = f"{event_name} {event_description} {event_location} {host_name} {speakers_text} {event_detail}"

    # Count keyword matches
    match_count = 0
    keyword_count = len(keywords)

    if keyword_count == 0:
        return 0.0

    # Calculate match frequencies
    for keyword in keywords:
        keyword = keyword.lower()
        if keyword in all_text:
            # Calculate frequency of occurrence for weighting
            frequency = all_text.count(keyword)
            # More weight to keywords in title
            if keyword in event_name:
                match_count += 1.5
            else:
                match_count += min(1.0, 0.5 + (frequency / 10))

    # Calculate score (0.0 to 0.7 max for basic matching)
    raw_score = (match_count / keyword_count)
    return min(0.7, raw_score * 0.7)

def calculate_combined_score(event: Dict[str, Any]) -> float:
    """
    Calculate a combined score based on relevance and recency

    Args:
        event: Event dictionary with relevance_score and parsed_date

    Returns:
        Combined score between 0.0 and 1.0
    """
    relevance_score = event.get('relevance_score', 0.0)

    # Calculate recency score (1.0 for today, decreasing as event gets further away)
    parsed_date = event.get('parsed_date')

    # If we don't have a parsed date, rely only on relevance
    if not parsed_date:
        return relevance_score

    days_until_event = (parsed_date - CURRENT_DATE).days

    # Normalize to a 0-1 scale (closer to 1 means more recent)
    # Use a logarithmic scale to prevent far-future events from getting too low a score
    recency_score = 1.0 / (1.0 + math.log(1 + max(0, days_until_event)))

    # Store the recency score for reference
    event['recency_score'] = recency_score

    # Calculate combined score with configurable weight
    # Formula: (1-w) * relevance + w * recency
    combined_score = (1 - RECENCY_WEIGHT) * relevance_score + RECENCY_WEIGHT * recency_score

    return combined_score

def find_top_events(keywords: List[str], max_results: int = 5, user_summary: str = "") -> List[Dict[str, Any]]:
    """
    Find the top events for the given keywords and user summary

    Args:
        keywords: List of keywords to match
        max_results: Maximum number of results to return
        user_summary: User's self-description and interests

    Returns:
        List of event dictionaries with relevance scores
    """
    logger.info(f"Finding top {max_results} events for keywords: {keywords}")
    if user_summary:
        logger.info(f"Using user summary: {user_summary[:50]}...")

    # Step 1: Load events from CSV
    all_events = load_events_from_csv()

    if not all_events:
        logger.warning("No events found to analyze")
        return []

    # Step 2: Filter to future events only
    future_events = [event for event in all_events if is_future_event(event)]

    if not future_events:
        logger.warning("No future events found")
        return []

    logger.info(f"Found {len(future_events)} future events out of {len(all_events)} total events")

    # Step 3: Analyze relevance of each future event with user_summary
    analyzed_events = []
    for event in future_events:
        logger.info(f"Processing event: {event.get('event_name')}")

        # Analyze relevance with user summary
        relevance_result = analyze_event_relevance(event, keywords, user_summary)

        # Add relevance data to event
        event['relevance_score'] = relevance_result.get('relevance_score', 0.0)
        event['relevance_highlight'] = relevance_result.get('highlight', 'No highlight available')

        analyzed_events.append(event)

    # Step 4: Calculate combined scores (relevance + recency)
    for event in analyzed_events:
        event['combined_score'] = calculate_combined_score(event)

    # Step 5: Sort by combined score (highest first)
    sorted_events = sorted(analyzed_events, key=lambda x: x.get('combined_score', 0.0), reverse=True)

    # Step 6: Return top results
    logger.info(f"Returning top {min(max_results, len(sorted_events))} events")
    return sorted_events[:max_results]

def format_date(date_str: str) -> str:
    """
    Format date string for display

    Args:
        date_str: Date string to format

    Returns:
        Formatted date string
    """
    if not date_str or date_str == 'Not specified':
        return 'Date not specified'

    try:
        # Try various date formats
        date_formats = [
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%m/%d/%Y',
            '%Y/%m/%d'
        ]

        # Handle combined date and time strings
        if ' ' in date_str:
            # Check if it's a date and time combination
            parts = date_str.split()
            if len(parts) >= 2:
                # Try to parse just the date part
                date_part = parts[0]
                for fmt in date_formats:
                    try:
                        dt = datetime.strptime(date_part, fmt)
                        # If successful, format the date and add back the time
                        return f"{dt.strftime('%A, %B %d, %Y')} at {' '.join(parts[1:])}"
                    except ValueError:
                        continue

        # Try parsing the entire string
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%A, %B %d, %Y")
            except ValueError:
                continue

        # Fall back to the parsed_date if available
        parsed_date = parse_event_date(date_str)
        if parsed_date:
            return parsed_date.strftime("%A, %B %d, %Y")

        # If all else fails, return the original string
        return date_str

    except Exception as e:
        logger.error(f"Error formatting date {date_str}: {str(e)}")
        return date_str


# Store logs for display
logs_buffer = []

# Custom logging handler to capture logs
class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        logs_buffer.append(log_entry)
        # Keep only the last 100 log entries
        while len(logs_buffer) > 100:
            logs_buffer.pop(0)

# Add buffer handler to logger
buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(buffer_handler)



# @app.route('/api/search_events', methods=['POST'])
def search_events(data, jsonify):
    """API endpoint to search for events"""
    keywords = data.get('keywords', '').split(',')
    keywords = [k.strip() for k in keywords if k.strip()]
    user_summary = data.get('user_summary', '')

    if not keywords:
        return jsonify({"success": False, "error": "No keywords provided"}), 400

    try:
        # Set max results to 10 (more than the 5 default)
        max_results = 10

        # Find top events for the keywords with user summary
        events = find_top_events(keywords, max_results=max_results, user_summary=user_summary)

        # Format dates for display
        for event in events:
            event_date = event.get('event_date', '')
            event_time = event.get('event_time', '')

            if event_date and event_time:
                event['formatted_date'] = f"{format_date(event_date)} at {event_time}"
            elif event_date:
                event['formatted_date'] = format_date(event_date)
            else:
                event['formatted_date'] = format_date(event.get('event_date_time', 'Date not specified'))

        return jsonify({
            "success": True,
            "events": events
        })
    except Exception as e:
        logger.error(f"Error in search_events: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500



# # @app.route('/api/keywords')
# def get_keywords():
#     """Get suggested keywords"""
#     try:
#         # Default keywords suggestions
#         default_keywords = ["AI", "machine learning", "startup", "venture capital", "blockchain"]
#         auto_search = request.args.get('auto_search') == 'true'

#         return jsonify({
#             "success": True,
#             "keywords": default_keywords,
#             "auto_search": auto_search
#         })
#     except Exception as e:
#         logger.error(f"Error getting keywords: {str(e)}")
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# def main():
#     """Main function to run the script"""
#     # try:
#     # Parse command line arguments
#     import argparse
#     parser = argparse.ArgumentParser(description='Combined Event Search Agent')
#     parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
#     parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
#     parser.add_argument('--debug', action='store_true', help='Run in debug mode')
#     parser.add_argument('--csv', type=str, help='Path to CSV file with events')
#     parser.add_argument('--recency-weight', type=float, help='Weight for recency in scoring (0.0-1.0, default: 0.2)')

#     args = parser.parse_args()

#     # Set CSV file path if provided
#     global CSV_FILE_PATH
#     if args.csv:
#         CSV_FILE_PATH = args.csv
#         logger.info(f"Using CSV file: {CSV_FILE_PATH}")

#     # Set recency weight if provided
#     global RECENCY_WEIGHT
#     if args.recency_weight is not None:
#         RECENCY_WEIGHT = max(0.0, min(1.0, args.recency_weight))
#         logger.info(f"Setting recency weight to {RECENCY_WEIGHT}")

#     # Log startup information
#     logger.info(f"Starting Combined Event Search Agent")
#     logger.info(f"Debug mode: {args.debug}")
#     logger.info(f"CSV file: {CSV_FILE_PATH}")
#     logger.info(f"Recency weight: {RECENCY_WEIGHT}")

#     # Verify that the CSV file exists
#     if not os.path.exists(CSV_FILE_PATH):
#         logger.error(f"CSV file not found: {CSV_FILE_PATH}")
#         logger.error("Please make sure the CSV file exists and is accessible")
#         return

#     # Verify that we can load events from the CSV file
#     events = load_events_from_csv()
