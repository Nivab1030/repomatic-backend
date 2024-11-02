from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, List
import asyncio
from datetime import datetime, timezone
from fastapi.middleware.cors import CORSMiddleware

from .github_collector import GitHubCollector
from .content_processor import ContentProcessor
from .content_generator import ContentGenerator
from .content_enricher import ContentEnricher

app = FastAPI(title="GitHub Content Pipeline API")

# Add this after creating the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Be more specific in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GithubFetchRequest(BaseModel):
    repo_name: str
    github_token: str
    days_back: int = 3

class ContentGenerationRequest(BaseModel):
    processed_content: Dict
    content_type: str
    selected_categories: Optional[List[str]] = None

class EnrichmentRequest(BaseModel):
    repo_name: str
    selected_items: List[Dict]
    github_token: str

@app.post("/api/fetch-github-content")
async def fetch_github_content(request: GithubFetchRequest):
    try:
        # Initialize collector with the provided repo and token
        collector = GitHubCollector(
            repo_name=request.repo_name,
            github_token=request.github_token
        )
        
        # Fetch GitHub data
        async with await collector.get_session() as session:
            tasks = [
                collector.async_fetch_pulls(session, request.days_back),
                collector.async_fetch_issues(session, request.days_back),
                collector.async_fetch_commits(session, request.days_back)
            ]
            pulls, issues, commits = await asyncio.gather(*tasks)
            
        activity_data = {
            'pulls': pulls,
            'issues': issues,
            'commits': commits
        }

        # Process the content
        processor = ContentProcessor()
        processed_content = processor.process(activity_data)

        return {
            "metadata": {
                "repository": request.repo_name,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "days_back": request.days_back,
                "total_items": {
                    "pulls": len(pulls),
                    "issues": len(issues),
                    "commits": len(commits)
                }
            },
            "processed_content": processed_content
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrich-content")
async def enrich_content(request: EnrichmentRequest):
    try:
        enricher = ContentEnricher(github_token=request.github_token)
        enriched_content = enricher.enrich_content(
            items=request.selected_items,
            repo_name=request.repo_name
        )
        
        return {
            "metadata": {
                "repository": request.repo_name,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "total_items": len(enriched_content)
            },
            "enriched_content": enriched_content
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-content")
async def generate_content(request: ContentGenerationRequest):
    try:
        generator = ContentGenerator()
        
        # Log the incoming request for debugging
        print("Received content generation request:", request)
        
        # Extract the content from the processed_content
        content_to_process = request.processed_content
        
        # Generate content based on type
        generated_content = generator.generate_content(
            content_to_process,  # Pass the entire categorized content
            content_type=request.content_type
        )
        
        # Log the generated content
        print("Generated content:", generated_content)

        response = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "content_type": request.content_type,
                "selected_categories": request.selected_categories
            },
            "generated_content": generated_content
        }
        
        return response

    except Exception as e:
        print(f"Error generating content: {str(e)}")
        print(f"Full error details: ", e.__dict__)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)