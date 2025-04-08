"""
Company Recommender Module

This module provides functionality to recommend companies based on user input and keywords.
"""

import logging
import random
import os
import json
import httpx
from typing import List, Dict, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class CompanyRecommender:
    """Recommends companies based on user input and keywords."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls, flow_controller=None):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = CompanyRecommender(flow_controller)
        return cls._instance
    
    def __init__(self, flow_controller=None):
        """Initialize the company recommender."""
        self.flow_controller = flow_controller
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        logger.info(f"Loaded Gemini API key: {self.gemini_api_key[:10] if self.gemini_api_key else 'Not found'}")
        
        # Sample companies for testing
        self.sample_companies = [
            {
                "name": "TechCorp Solutions",
                "description": "Enterprise software for sales teams",
                "website": "https://techcorp.example.com",
                "relevance_score": 0.92
            },
            {
                "name": "DataFlow Analytics",
                "description": "AI-powered business intelligence platform",
                "website": "https://dataflow.example.com",
                "relevance_score": 0.87
            },
            {
                "name": "CloudScale Systems",
                "description": "Cloud infrastructure for growing businesses",
                "website": "https://cloudscale.example.com",
                "relevance_score": 0.81
            },
            {
                "name": "MarketPulse CRM",
                "description": "Customer relationship management for B2B sales",
                "website": "https://marketpulse.example.com",
                "relevance_score": 0.78
            },
            {
                "name": "LeadGen Pro",
                "description": "Lead generation and qualification platform",
                "website": "https://leadgen.example.com",
                "relevance_score": 0.75
            }
        ]
    
    async def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate company recommendations based on user input and keywords."""
        try:
            # In a real implementation, this would use the keywords and user data
            # to generate personalized recommendations
            
            # For now, return sample companies with randomized relevance scores
            recommendations = self.sample_companies.copy()
            
            # Randomize relevance scores slightly for demo purposes
            for company in recommendations:
                company["relevance_score"] = round(company["relevance_score"] * random.uniform(0.95, 1.05), 2)
                # Cap at 1.0
                if company["relevance_score"] > 1.0:
                    company["relevance_score"] = 1.0
            
            # Sort by relevance score
            recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            logger.info(f"Generated {len(recommendations)} company recommendations")
            return recommendations
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self.sample_companies
