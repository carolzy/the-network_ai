# Event Search Agent

A streamlined event finder application that combines the best features from the firecrawl_convostyle and atom-voice-search projects. This application scrapes events from lu.ma, analyzes their relevance to user-provided keywords using the Gemini 2.0 Flash model, and displays the most relevant upcoming events.

## Features

- **Event Scraping**: Uses Firecrawl API to scrape events from lu.ma
- **Relevance Analysis**: Analyzes event relevance using Google's Gemini 2.0 Flash model
- **Recency Filtering**: Only shows events happening in the next 3 weeks
- **Web Interface**: Clean, responsive UI for searching and viewing events
- **Real-time Logs**: View logs in real-time to track the scraping and analysis process
- **API Integration**: Can integrate with atom-voice-search for keyword generation

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up your environment variables in `.env`:
   ```
   FIRECRAWL_API_KEY=your_firecrawl_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

## Usage

### Web Interface

Run the application as a web server:

```
python event_search_agent.py --server
```

Then open your browser to http://localhost:9020

### Command Line

Search for events directly from the command line:

```
python event_search_agent.py --keywords "AI, startup, technology" --location "sf"
```

## API Endpoints

- `GET /` - Main web interface
- `POST /api/search` - Search for events based on keywords and location
- `GET /api/logs` - Get real-time logs
- `GET /api/keywords` - Get keywords from atom-voice-search (if integrated)

## Project Structure

- `event_search_agent.py` - Main application file
- `templates/` - HTML templates
- `static/` - CSS and JavaScript files
- `.env` - Environment variables
- `requirements.txt` - Python dependencies

## Integration with atom-voice-search

This project is designed to integrate with the atom-voice-search project for keyword generation. The `/api/keywords` endpoint provides a way to fetch keywords generated from voice input.
