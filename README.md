# NetworkAI: Event Search Agent

A conversational AI agent that helps founders find relevant events based on their business context. The application uses dynamic question generation to gather information about the user's business and then recommends events that match their interests.

## Project Overview

NetworkAI is designed to help founders and entrepreneurs discover networking events that are most relevant to their business. The system:

1. Engages users in a conversational onboarding flow to understand their business
2. Extracts keywords from their responses using the Gemini API
3. Searches for and ranks events from Luma based on relevance to the user's business
4. Presents the most relevant events with detailed information

## Folder Structure

The repository is organized into three main components:

### 1. `voice_integration/` (Core Application)

This is the **main application** that users should run to experience the full functionality. It contains:

- `app.py`: The main entry point for the application
- `flow_controller.py`: Manages the conversation flow and user journey
- `question_engine.py`: Generates dynamic questions using the Gemini API
- `event_scraper.py`: Connects to event sources to find relevant events
- `voice_processor.py`: Handles voice input/output (optional feature)
- `templates/` & `static/`: Frontend UI components

### 2. `event-search-final/` (Simplified Event Search)

A standalone implementation of just the event search functionality:

- `event_search_agent.py`: Simplified version of the event search
- `luma_event_integration.py`: Integration with Luma events

This folder is useful if you only want to implement the event search without the conversational interface.

### 3. `luma_event_scraper/` (Development Tools)

**Note: This folder is for development purposes only and not required for regular users.**

Contains tools used during development to scrape and analyze Luma events:

- `luma_advanced_scraper.py`: Advanced scraping tools for Luma events
- Pre-scraped event data (CSV files) for testing

## Required API Keys

The application requires only two API keys to function:

1. **Google Gemini API Key** (Required)
   - Used for dynamic question generation and keyword extraction
   - Get a key from [Google AI Studio](https://ai.google.dev/)

2. **Firecrawl API Key** (Required for live event data)
   - Used for scraping event data from Luma
   - Get a key from [Firecrawl](https://firecrawl.dev/)

3. **ElevenLabs API Key** (Optional)
   - Only needed if you want to use voice features
   - The application works perfectly fine without this

## Event Data Sources

The application sources event data from:

- **Luma Events**: A platform for discovering and hosting community events
- The system searches for events on lu.ma/sf and other Luma pages
- Events are ranked based on relevance to the user's business context
- By default, the application focuses on tech and startup events in major cities

## Setup Instructions

### Prerequisites

- Python 3.9+
- Required API keys (see above)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/carolzy/the-network_ai.git
   cd the-network_ai
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your API keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   FIRECRAWL_API_KEY=your_firecrawl_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key  # Optional
   ```

### Running the Application

To start the main application with the conversational interface:

```
python -m voice_integration.app
```

The application will be available at http://localhost:9003

## Features

- **Dynamic Question Generation**: Contextual questions based on previous responses
- **Keyword Extraction**: Intelligent extraction of relevant business keywords
- **Event Relevance Ranking**: Events are ranked by relevance to the user's business
- **Voice Interaction**: Optional voice-based interaction (requires ElevenLabs API key)
- **Detailed Event Information**: Event descriptions, dates, locations, and relevance scores

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.