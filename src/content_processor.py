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

    def process(self, activity_data: dict) -> dict:
        """
        Process the GitHub activity data and categorize it.
        
        Args:
            activity_data: Dictionary containing 'pulls', 'issues', and 'commits' data
            
        Returns:
            Dictionary of processed and categorized content
        """
        try:
            logger.info("Starting content processing")
            
            processed_content = {
                'code_changes': [],
                'bug_fixes': [],
                'features': [],
                'documentation': [],
                'other': []
            }
            
            # Process pull requests
            for pr in activity_data.get('pulls', []):
                category = self._categorize_item(pr)
                item_data = {
                    'type': 'pull_request',
                    'number': pr.get('number'),
                    'title': pr.get('title'),
                    'body': pr.get('body', ''),
                    'url': pr.get('url'),
                    'created_at': pr.get('created_at'),
                    'author': pr.get('author'),
                    'labels': pr.get('labels', [])
                }
                processed_content[category].append(item_data)
            
            # Process issues
            for issue in activity_data.get('issues', []):
                category = self._categorize_item(issue)
                item_data = {
                    'type': 'issue',
                    'number': issue.get('number'),
                    'title': issue.get('title'),
                    'body': issue.get('body', ''),
                    'url': issue.get('url'),
                    'created_at': issue.get('created_at'),
                    'author': issue.get('author'),
                    'labels': issue.get('labels', [])
                }
                processed_content[category].append(item_data)
            
            # Process commits
            for commit in activity_data.get('commits', []):
                category = self._categorize_item(commit)
                item_data = {
                    'type': 'commit',
                    'sha': commit.get('sha'),
                    'message': commit.get('message'),
                    'url': commit.get('url'),
                    'created_at': commit.get('created_at'),
                    'author': commit.get('author')
                }
                processed_content[category].append(item_data)
            
            logger.info("Content processing completed successfully")
            return processed_content
            
        except Exception as e:
            logger.error(f"Error in process method: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _categorize_item(self, item: dict) -> str:
        """
        Categorize an item based on its title, body, and labels.
        """
        title = item.get('title', '').lower()
        body = item.get('body', '').lower()
        labels = [label.lower() for label in item.get('labels', [])]
        
        # Check for documentation changes
        if any(keyword in title or keyword in body for keyword in ['doc', 'docs', 'documentation']):
            return 'documentation'
        
        # Check for bug fixes
        if any(keyword in title or keyword in body or keyword in labels for keyword in ['bug', 'fix', 'hotfix']):
            return 'bug_fixes'
        
        # Check for features
        if any(keyword in title or keyword in body or keyword in labels for keyword in ['feature', 'enhancement', 'feat']):
            return 'features'
        
        # Check for code changes
        if any(keyword in title or keyword in body for keyword in ['refactor', 'perf', 'performance', 'test']):
            return 'code_changes'
        
        # Default category
        return 'other'