# Event Search Agent

A conversational AI agent that helps founders find relevant events based on their business context. The application uses dynamic question generation to gather information about the user's business and then recommends events that match their interests.

## Project Structure

The project consists of several components:

1. **Voice Integration**: The core conversational interface that guides users through an onboarding process
2. **Event Search**: Integration with Luma Events to find relevant events based on user keywords
3. **Luma Event Scraper**: Tools for scraping and analyzing events from Luma's platform

## Key Features

- **Dynamic Question Generation**: Uses Google's Gemini API to generate contextual questions
- **Keyword Extraction**: Analyzes user responses to extract relevant keywords
- **Event Relevance Analysis**: Ranks events based on relevance to user's business context
- **Voice Interaction**: Supports voice-based interaction for a natural conversation experience

## Setup Instructions

### Prerequisites

- Python 3.9+
- API keys for:
  - Google Gemini API
  - Firecrawl API (for event scraping)

### Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd event-search-agent
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your API keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   FIRECRAWL_API_KEY=your_firecrawl_api_key
   ```

### Running the Application

To start the voice integration and event search interface:

```
python -m voice_integration.app
```

The application will be available at http://localhost:9003

## Components

### Voice Integration

The voice integration module handles the conversational flow with users:

- `app.py`: Main application entry point
- `flow_controller.py`: Manages the multi-step onboarding process
- `question_engine.py`: Generates dynamic questions using the Gemini API
- `voice_processor.py`: Handles voice input/output

### Event Search

The event search functionality finds and ranks events:

- `event_scraper.py`: Scrapes event data from Luma
- `luma_event_integration.py`: Integrates with the Luma platform

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.