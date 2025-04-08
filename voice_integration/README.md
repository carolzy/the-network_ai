# Voice-Enabled Event Search Integration

This integration combines the voice search capabilities from the atom-voice-search project with the enhanced event search functionality using Firecrawl API and Gemini AI.

## Features

- Voice-based keyword extraction and question generation
- Real-time event search from Luma Events using Firecrawl API
- Event relevance analysis using Google's Gemini AI
- Combined scoring system that balances relevance and recency
- Interactive web interface for searching and viewing events

## Setup Instructions

1. **Environment Setup**:
   - Create a virtual environment: `python -m venv venv`
   - Activate the virtual environment: `source venv/bin/activate`
   - Install dependencies: `pip install -r requirements.txt`

2. **API Keys**:
   - Make sure your `.env` file contains the necessary API keys:
     - `FIRECRAWL_API_KEY`: For scraping events from Luma
     - `GEMINI_API_KEY`: For analyzing event relevance
     - `ELEVENLABS_API_KEY`: For text-to-speech (optional)
     - `OPENAI_API_KEY`: For keyword extraction (optional)

3. **Running the Application**:
   - Start the server: `python app.py`
   - Access the web interface at: `http://localhost:9001` (or the port specified in your .env file)

## Components

- `app.py`: Main application server using Quart for async web handling
- `event_scraper.py`: Enhanced event scraper using Firecrawl API and Gemini
- `flow_controller.py`: Manages the conversation flow and keyword extraction
- `question_engine.py`: Generates questions based on extracted keywords
- `voice_processor.py`: Handles speech recognition and processing
- `user_memory.py`: Manages user preferences and history

## Usage

1. Access the web interface
2. Use the microphone button to start voice input
3. The system will extract keywords from your speech
4. Events related to these keywords will be displayed
5. You can also manually enter keywords and location in the search form

## Testing

- `test_event_scraper.py`: Test the event scraper functionality
- `test_ui.html`: A simple UI for testing the integration

## Notes

- The event search functionality uses real data from Luma Events via Firecrawl API
- Events are ranked based on both relevance to keywords and recency
- The voice processing requires a microphone and may not work in all browsers
