from github import Github, GithubException
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
import logging
import traceback
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging with more details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ContentProcessor:
    def __init__(self, config=None):
        self.config = config if config is not None else {}
        self.github_token = self._get_github_token()
        self.github = Github(self.github_token)

    def _get_github_token(self):
        # Use user-provided token if available, otherwise fall back to default
        user_token = self.config.get('github_token', '')
        if isinstance(user_token, str):
            user_token = user_token.strip()
        
        default_token = os.getenv('GITHUB_TOKEN', '')
        if isinstance(default_token, str):
            default_token = default_token.strip()
        
        if user_token:
            return user_token
        elif default_token:
            return default_token
        else:
            raise ValueError("No GitHub token provided and no default token found in environment")

    def fetch_pull_requests(self, repo_name: str, days_back: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch pull requests from the repository within the specified time period.
        """
        try:
            logger.info(f"Fetching PRs from {repo_name} for the last {days_back} days")
            
            try:
                logger.debug(f"Accessing repository {repo_name}...")
                repo = self.github.get_repo(repo_name)
                logger.debug(f"Successfully accessed repository: {repo.full_name}")
            except GithubException as e:
                logger.error(f"Failed to access repository {repo_name}: {str(e)}")
                logger.error(f"Error status: {e.status}, Data: {e.data}")
                if e.status == 404:
                    raise Exception(f"Repository '{repo_name}' not found. Please check the repository name.")
                raise Exception(f"Failed to access repository: {str(e)}")
            
            # Create timezone-aware datetime for comparison
            since_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            pull_requests = []
            
            try:
                logger.debug("Fetching pull requests...")
                pulls = repo.get_pulls(state='all', sort='created', direction='desc')
                logger.debug(f"Got pulls object: {pulls}")
                
                for pr in pulls:
                    try:
                        # Ensure PR created_at is timezone-aware
                        pr_created_at = pr.created_at.replace(tzinfo=timezone.utc) if pr.created_at.tzinfo is None else pr.created_at
                        
                        if pr_created_at < since_date:
                            break
                            
                        logger.debug(f"Processing PR #{pr.number}")
                        pr_data = {
                            'number': pr.number,
                            'title': pr.title,
                            'body': pr.body or '',
                            'created_at': pr_created_at.isoformat(),
                            'state': pr.state,
                            'url': pr.html_url,
                            'author': pr.user.login if pr.user else 'Unknown',
                            'labels': [label.name for label in pr.labels],
                            'merged': pr.merged if hasattr(pr, 'merged') else False
                        }
                        pull_requests.append(pr_data)
                        logger.debug(f"Successfully processed PR #{pr.number}: {pr.title}")
                        
                    except Exception as e:
                        logger.error(f"Error processing PR #{pr.number}: {str(e)}")
                        logger.error(traceback.format_exc())
                        continue

                logger.info(f"Successfully fetched {len(pull_requests)} PRs")
                result = {'pull_requests': pull_requests}
                logger.debug(f"Returning result: {result}")
                return result
                
            except GithubException as e:
                logger.error(f"Failed to fetch pull requests: {str(e)}")
                logger.error(f"Error status: {e.status}, Data: {e.data}")
                raise Exception(f"Failed to fetch pull requests: {str(e)}")

        except Exception as e:
            logger.error(f"Error in fetch_pull_requests: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def fetch_github_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to fetch content from GitHub.
        """
        try:
            repo_name = params.get('repo_name')
            days_back = params.get('days_back', 7)

            logger.debug(f"Received params: repo_name={repo_name}, days_back={days_back}")

            if not repo_name:
                raise ValueError("Repository name is required")
            
            if '/' not in repo_name:
                raise ValueError("Repository name must be in the format 'owner/repo'")

            logger.info(f"Starting content fetch for {repo_name}")
            
            try:
                # Fetch only pull requests for now
                content = self.fetch_pull_requests(repo_name, days_back)
                logger.debug(f"Fetched content: {content}")
                return content
            except Exception as e:
                logger.error(f"Error fetching pull requests: {str(e)}")
                logger.error(traceback.format_exc())
                raise Exception(f"Error fetching pull requests: {str(e)}")
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in fetch_github_content: {str(e)}")
            logger.error(traceback.format_exc())
            raise