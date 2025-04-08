#!/usr/bin/env python3
"""
Launcher script for the Voice-Enabled Event Search Integration
"""

import os
import sys
import subprocess
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('launcher')

def check_environment():
    """Check if the environment is properly set up"""
    
    # Load environment variables
    load_dotenv()
    
    # Check for required API keys
    required_keys = ['FIRECRAWL_API_KEY', 'GEMINI_API_KEY']
    missing_keys = [key for key in required_keys if not os.environ.get(key)]
    
    if missing_keys:
        logger.error(f"Missing required API keys: {', '.join(missing_keys)}")
        logger.error("Please add these keys to your .env file")
        return False
    
    # Check for Python dependencies
    try:
        import quart
        import google.generativeai
        import firecrawl
        import speech_recognition
    except ImportError as e:
        logger.error(f"Missing dependency: {str(e)}")
        logger.error("Please run: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Main function to run the application"""
    
    logger.info("Starting Voice-Enabled Event Search Integration")
    
    # Check environment
    if not check_environment():
        logger.error("Environment check failed. Please fix the issues and try again.")
        sys.exit(1)
    
    # Get port from environment or use default
    port = os.environ.get('PORT', '9001')
    
    # Run the application
    logger.info(f"Starting server on port {port}")
    try:
        subprocess.run([sys.executable, "app.py", "--port", port], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running application: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    
    logger.info("Application stopped")

if __name__ == "__main__":
    main()
