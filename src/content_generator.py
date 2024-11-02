from typing import Dict, List, Any
import logging
import traceback
import sys
from datetime import datetime
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ContentGenerator:
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)

    def generate_content(self, content: Dict[str, Any], content_type: str) -> Dict[str, Any]:
        try:
            # Generate the content using OpenAI
            generated_text = self._generate_with_openai(content, content_type)
            
            # Return in the expected format
            return {
                "content": generated_text,
                "contentType": content_type,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            raise

    def _generate_with_openai(self, content: Dict[str, Any], content_type: str) -> str:
        try:
            # Extract PRs and their commits
            prs = content.get('pull_requests', [])
            logger.info(f"Generating {content_type} content for {len(prs)} pull requests")
            
            # Create a summary of all PRs and their changes
            pr_summaries = []
            for pr in prs:
                commits_summary = "\n".join([
                    f"- {commit.get('message', '')}: {commit.get('explanation', '')}"
                    for commit in pr.get('commits', [])
                ])
                
                pr_summary = f"""
                PR #{pr['number']}: {pr['title']}
                {pr['body']}
                
                Commits:
                {commits_summary}
                """
                pr_summaries.append(pr_summary)

            # Create prompt based on content type
            prompt = self._create_prompt(pr_summaries, content_type)
            
            logger.debug("Sending request to OpenAI...")
            # Generate content using OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a technical writer creating content from GitHub pull requests."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )

            generated_text = response.choices[0].message.content.strip()
            logger.info("Successfully generated content")
            
            return generated_text

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _create_prompt(self, pr_summaries: List[str], content_type: str) -> str:
        summaries_text = "\n\n".join(pr_summaries)
        
        prompts = {
            'blog_post': f"""
                Write a technical blog post about the following changes:
                {summaries_text}
                
                Focus on the key features, improvements, and their impact.
                Format the post with proper headings, sections, and technical details.
                """,
            'release_notes': f"""
                Create release notes from these changes:
                {summaries_text}
                
                Group the changes by type (features, fixes, improvements).
                Keep it concise but informative.
                """,
            'tweet': f"""
                Write an engaging tweet thread (3-5 tweets) about these updates:
                {summaries_text}
                
                Focus on the most important changes and their benefits.
                Format with tweet numbers (1/X).
                Keep each tweet within 280 characters.
                """,
            'feature_page': f"""
                Create a feature page describing these changes:
                {summaries_text}
                
                Include:
                - Feature overview
                - Key benefits
                - Technical details
                - Example use cases
                """
        }
        
        return prompts.get(content_type, prompts['blog_post'])