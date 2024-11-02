from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
import logging
import traceback
import sys
import os
from dotenv import load_dotenv
from pathlib import Path

# Import our custom classes
from .content_processor import ContentProcessor
from .content_enricher import ContentEnricher
from .content_generator import ContentGenerator

# Load environment variables from .env file
env_path = Path(__file__).parents[2] / '.env'  # Go up two directories to find .env
load_dotenv(dotenv_path=env_path)

# Configure logging with more details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GithubContentRequest(BaseModel):
    repo_name: str
    github_token: Optional[str] = None
    days_back: int = 7

    @validator('repo_name')
    def validate_repo_name(cls, v):
        if not v or '/' not in v:
            raise ValueError("Repository name must be in the format 'owner/repo'")
        return v

    @validator('days_back')
    def validate_days_back(cls, v):
        if v < 1 or v > 30:
            raise ValueError("days_back must be between 1 and 30")
        return v

class EnrichmentRequest(BaseModel):
    repo_name: str
    github_token: str
    selected_items: List[Dict[str, Any]]

class GenerationRequest(BaseModel):
    processed_content: Dict[str, Any]
    content_type: str

@app.post("/api/fetch-github-content")
async def fetch_github_content(request: GithubContentRequest):
    try:
        logger.info(f"Starting fetch_github_content with repo: {request.repo_name}")
        logger.debug(f"Request data: repo_name={request.repo_name}, days_back={request.days_back}")
        
        try:
            # Create processor with config including optional token
            config = {}
            if request.github_token:
                config['github_token'] = request.github_token
                
            logger.debug("Creating ContentProcessor...")
            processor = ContentProcessor(config)
            logger.debug("ContentProcessor initialized successfully")
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logger.error(f"Failed to initialize ContentProcessor: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=401,
                detail=f"GitHub authentication failed: {str(e)}"
            )
            
        try:
            params = {
                "repo_name": request.repo_name,
                "days_back": request.days_back
            }
            
            logger.debug(f"Calling fetch_github_content with params: {params}")
            content = processor.fetch_github_content(params)
            
            if not isinstance(content, dict):
                raise ValueError(f"Expected dict, got {type(content)}")
                
            if 'pull_requests' not in content:
                raise ValueError("Response missing 'pull_requests' key")
            
            if not content.get('pull_requests'):
                logger.info("No pull requests found")
                return {
                    'pull_requests': [],
                    'message': 'No pull requests found in the specified time period'
                }
            
            logger.info(f"Successfully fetched {len(content['pull_requests'])} pull requests")
            return content
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in fetch_github_content: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch GitHub content: {str(e)}"
        )

@app.post("/api/enrich-content")
async def enrich_content(request: EnrichmentRequest):
    try:
        logger.info(f"Starting content enrichment for repo: {request.repo_name}")
        
        # Get OpenAI API key from environment with debug logging
        openai_api_key = os.getenv('OPENAI_API_KEY')
        logger.debug(f"OpenAI API key present: {'Yes' if openai_api_key else 'No'}")
        
        if not openai_api_key:
            logger.error("OpenAI API key not found in environment variables")
            logger.debug(f"Available environment variables: {list(os.environ.keys())}")
            raise HTTPException(
                status_code=500,
                detail="OpenAI API key not configured"
            )

        try:
            # Create enricher with config including optional token
            config = {}
            if request.github_token:
                config['github_token'] = request.github_token
                
            enricher = ContentEnricher(config)
            
            enriched_content = enricher.enrich_content(
                repo_name=request.repo_name,
                selected_items=request.selected_items
            )
            
            return enriched_content
            
        except Exception as e:
            logger.error(f"Error enriching content: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to enrich content: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in enrich_content: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enrich content: {str(e)}"
        )

@app.post("/api/generate-content")
async def generate_content(request: GenerationRequest):
    try:
        logger.info(f"Starting content generation with type: {request.content_type}")
        
        # Get OpenAI API key from environment
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            raise HTTPException(
                status_code=500,
                detail="OpenAI API key not configured"
            )

        try:
            generator = ContentGenerator(openai_api_key=openai_api_key)
            
            generated_content = generator.generate_content(
                content=request.processed_content,
                content_type=request.content_type
            )
            
            return generated_content
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate content: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_content: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate content: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up application...")
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        logger.warning("OpenAI API key not found in environment variables!")
    else:
        logger.info("OpenAI API key found in environment variables")