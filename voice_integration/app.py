import logging
import time
from quart import Quart, render_template, request, jsonify, send_file
# from voice_integration.flow_controller import FlowController
# from voice_integration.voice_processor import VoiceProcessor
# from voice_integration.question_engine import QuestionEngine
# from voice_integration.company_recommender import CompanyRecommender
from flow_controller import FlowController
from voice_processor import VoiceProcessor
from question_engine import QuestionEngine
from company_recommender import CompanyRecommender
# import asyncio
from event_search_agent import search_events as search_events_api


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Quart app
app = Quart(__name__, static_folder="static", template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Version for cache busting
VERSION = str(int(time.time()))

# Initialize core components
flow_controller = FlowController()
voice_processor = VoiceProcessor(flow_controller)
question_engine = QuestionEngine()
company_recommender = CompanyRecommender(flow_controller)

@app.route("/")
async def index():
    # Simply use await directly
    await flow_controller.reset()
    greeting = await question_engine.get_question("product")
    first_question = await flow_controller.get_question("product")
    return await render_template("index.html", greeting=greeting, first_question=first_question, version=VERSION)

@app.route("/search/events", methods=['GET','POST'])
async def event_search():
    # Render the landing page with the chat interface and keyword generator
    await flow_controller.reset()

    form = await request.form
    summary = form.get('summary')
    keywords = form.get('keywords')

    context = {"summary": summary, "keywords": keywords}
    return await render_template("event_search.html", version=VERSION, **context)

@app.route("/landing")
async def landing_page():
    # Render the landing page with the chat interface and keyword generator
    await flow_controller.reset()
    return await render_template("landing_page.html", version=VERSION)

@app.route("/api/onboarding", methods=["POST"])
async def onboarding_step():
    data = await request.get_json()
    step = data.get("step")
    answer = data.get("answer", "")
    logger.info(f"Onboarding: {step} => {answer}")

    await flow_controller.store_answer(step, answer)
    next_step = flow_controller.get_next_step(step)

    if next_step == "complete":
        cleaned_keywords = await flow_controller.clean_keywords()
        recommendations = await company_recommender.generate_recommendations()
        return jsonify({
            "success": True,
            "completed": True,
            "keywords": cleaned_keywords,
            "recommendations": recommendations
        })

    question = await flow_controller.get_question(next_step)
    audio_data = await voice_processor.text_to_speech(question)
    return jsonify({
        "success": True,
        "step": next_step,
        "question": question,
        "audio": audio_data,
        "keywords": flow_controller.keywords  # Always include current keywords
    })

@app.route("/api/get_question", methods=["GET"])
async def get_question():
    step = request.args.get("step", "product")
    question = await flow_controller.get_question(step)
    audio_data = await voice_processor.text_to_speech(question)
    return jsonify({
        "success": True,
        "question": question,
        "audio": audio_data,
        "keywords": flow_controller.keywords  # Always include current keywords
    })

@app.route("/api/recommendations", methods=["GET"])
async def get_recommendations():
    recs = await company_recommender.generate_recommendations()
    return jsonify(recs)

@app.route("/api/text_to_speech", methods=["POST"])
async def tts():
    data = await request.get_json()
    text = data.get("text", "")
    audio_data = await voice_processor.text_to_speech(text)
    return jsonify({"audio": audio_data})

@app.route("/api/voice_interaction", methods=["POST"])
async def voice_interaction():
    if not voice_processor:
        return jsonify({"error": "Voice processor not initialized"}), 500
    try:
        data = await request.get_json()
        text = data.get("text")
        step = data.get("step", "product")  # This is the current step
        if not text:
            return jsonify({"error": "No text provided"}), 400

        logger.info(f"Processing voice interaction for step: {step}, text: {text}")

        await flow_controller.store_answer(step, text)
        next_step = await flow_controller.get_next_step(step)

        logger.info(f"Next step after {step}: {next_step}")

        if next_step == "complete":
            logger.info("Flow complete, generating keywords and recommendations")
            logger.info(f"Current keywords before cleaning: {flow_controller.keywords}")
            cleaned_keywords = await flow_controller.clean_keywords()
            logger.info(f"Cleaned keywords: {cleaned_keywords}")
            recommendations = await company_recommender.generate_recommendations()
            logger.info(f"Generated recommendations: {recommendations}")
            return jsonify({
                "success": True,
                "completed": True,
                "text": "You're all set! Generating your results.",
                "keywords": cleaned_keywords,
                "recommendations": recommendations,
                "show_recommendations_tab": True
            })

        question = await flow_controller.get_question(next_step)
        audio = await voice_processor.text_to_speech(question)
        # Always include current keywords in the response
        current_keywords = await flow_controller.clean_keywords()

        return jsonify({
            "success": True,
            "text": question,
            "next_step": next_step,
            "audio": audio,
            "keywords": current_keywords  # Always include current keywords
        })
    except Exception as e:
        logger.error(f"Voice interaction failed: {str(e)}")
        return jsonify({"error": "Voice processing failed"}), 500

@app.route("/onboarding_data.csv")
async def download_onboarding_data():
    return await send_file("onboarding_data.csv", as_attachment=True)

@app.after_request
async def add_header(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/api/save_interaction", methods=["POST"])
async def save_interaction():
    """Save user interaction data."""
    try:
        data = await request.get_json()
        logger.info(f"Saving interaction data: {data}")

        # Here you would typically save this data to a database
        # For now, we'll just log it and return success

        return jsonify({
            "success": True,
            "message": "Interaction saved successfully"
        })
    except Exception as e:
        logger.error(f"Error saving interaction: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/keywords", methods=["GET"])
async def get_keywords():
    """Get the current keywords."""
    try:
        # Initialize flow controller if not already done
        global flow_controller
        if flow_controller is None:
            flow_controller = FlowController()

        # Return the current keywords
        current_keywords = await flow_controller.clean_keywords()

        # Get the user summary
        user_summary = flow_controller.get_user_summary()

        return jsonify({
            "success": True,
            "keywords": current_keywords,
            "user_summary": user_summary
        })
    except Exception as e:
        logger.error(f"Error getting keywords: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "keywords": [],
            "user_summary": ""
        }), 500

@app.route("/recommendations")
async def recommendations_page():
    return await render_template("recommendations.html")

@app.route("/test_ui.html")
async def test_ui():
    """Serve the test UI HTML file."""
    return await send_file("test_ui.html")

@app.route("/api/search_events", methods=["POST"])
async def search_events():
    """Search for events based on keywords and location."""
    data = await request.get_json()
    return search_events_api(data, jsonify)

    data = await request.get_json()
    keywords = data.get("keywords", [])
    location = data.get("location", "SF")

    logger.info(f"Searching for events with keywords: {keywords}, location: {location}")

    # Use the Firecrawl API to scrape Luma events
    # This is a mock implementation for now
    # In a production environment, you would integrate with the firecrawl_luma module

    # Mock events data for demonstration
    events = [
        {
            "title": "AI Safety and Ethics Conference",
            "date": "2025-04-15T09:00:00-07:00",
            "location": f"{location} Convention Center",
            "description": "Join industry leaders to discuss the latest developments in AI safety and ethical considerations for voice assistants and generative AI systems.",
            "url": "https://lu.ma/ai-safety-conference",
            "matching_keywords": ["AI Safety", "Voice Assistants", "Ethics"]
        },
        {
            "title": "Enterprise AI Solutions Summit",
            "date": "2025-04-22T10:00:00-07:00",
            "location": f"Downtown {location}",
            "description": "A gathering of enterprise solution providers and buyers focused on implementing AI safely and effectively in corporate environments.",
            "url": "https://lu.ma/enterprise-ai-summit",
            "matching_keywords": ["Enterprise", "AI Solutions", "Corporate"]
        },
        {
            "title": "Voice Technology Meetup",
            "date": "2025-04-10T18:30:00-07:00",
            "location": f"{location} Tech Hub",
            "description": "Monthly meetup for voice technology enthusiasts and professionals. Share insights, network, and learn about the latest advancements.",
            "url": "https://lu.ma/voice-tech-meetup",
            "matching_keywords": ["Voice Assistants", "Technology"]
        }
    ]

    # Filter events based on keywords
    if keywords:
        filtered_events = []
        for event in events:
            # Check if any keyword matches the event title or description
            for keyword in keywords:
                if (keyword.lower() in event["title"].lower() or
                    keyword.lower() in event["description"].lower()):
                    # Add matching keyword to the event
                    if "matching_keywords" not in event:
                        event["matching_keywords"] = []
                    if keyword not in event["matching_keywords"]:
                        event["matching_keywords"].append(keyword)

                    # Add event to filtered list if not already added
                    if event not in filtered_events:
                        filtered_events.append(event)

        events = filtered_events

    return jsonify({
        "success": True,
        "events": events
    })

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Atom Voice Search Server')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=9003, help='Port to bind to')
    args = parser.parse_args()

    app.run(host=args.host, port=args.port)
