import os
from github import Github
from typing import List, Dict, Any
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ContentEnricher:
    def __init__(self, config=None):
        self.config = config if config is not None else {}
        self.github_token = self._get_github_token()
        self.openai_api_key = self._get_openai_key()
        
        # Initialize clients
        self.github = Github(self.github_token)
        self.openai_client = OpenAI(api_key=self.openai_api_key)

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

    def _get_openai_key(self):
        return os.getenv('OPENAI_API_KEY')

    def enrich_content(self, repo_name: str, selected_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enrich the selected content items with additional information.
        """
        try:
            logger.info(f"Starting content enrichment for {len(selected_items)} items")
            
            # Get repository
            repo = self.github.get_repo(repo_name)
            enriched_prs = []

            for item in selected_items:
                try:
                    if item['type'] == 'pull_request':
                        pr_number = item['number']
                        pr = repo.get_pull(pr_number)
                        
                        # Get PR details
                        files_changed = list(pr.get_files())
                        commits = list(pr.get_commits())
                        
                        # Prepare file changes summary
                        file_changes = [{
                            'filename': f.filename,
                            'additions': f.additions,
                            'deletions': f.deletions,
                            'status': f.status
                        } for f in files_changed]

                        # Prepare commit summary
                        commit_summary = [{
                            'sha': c.sha,
                            'message': c.commit.message,
                            'author': c.commit.author.name if c.commit.author else 'Unknown'
                        } for c in commits]

                        # Enrich with OpenAI analysis
                        analysis = self._analyze_pr_with_ai(pr, file_changes, commit_summary)

                        enriched_pr = {
                            'number': pr_number,
                            'title': pr.title,
                            'body': pr.body or '',
                            'state': pr.state,
                            'merged': pr.merged,
                            'files_changed': file_changes,
                            'commits': commit_summary,
                            'analysis': analysis
                        }
                        
                        enriched_prs.append(enriched_pr)
                        logger.debug(f"Successfully enriched PR #{pr_number}")
                        
                except Exception as e:
                    logger.error(f"Error enriching item {item}: {str(e)}")
                    continue

            return {'pull_requests': enriched_prs}
            
        except Exception as e:
            logger.error(f"Error in enrich_content: {str(e)}")
            raise

    def _analyze_pr_with_ai(self, pr, file_changes, commit_summary) -> Dict[str, str]:
        """
        Use OpenAI to analyze the PR and generate insights.
        """
        try:
            # Prepare context for AI
            context = f"""
            Pull Request Title: {pr.title}
            Description: {pr.body or 'No description provided'}
            
            Files Changed: {len(file_changes)}
            Total Commits: {len(commit_summary)}
            
            File Changes Summary:
            {self._format_file_changes(file_changes)}
            
            Commit Messages:
            {self._format_commits(commit_summary)}
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a code review assistant. Analyze the pull request and provide insights."},
                    {"role": "user", "content": context}
                ]
            )

            return {
                'summary': response.choices[0].message.content,
                'complexity': self._assess_complexity(file_changes),
                'impact': self._assess_impact(file_changes, commit_summary)
            }
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {str(e)}")
            return {
                'summary': "AI analysis failed",
                'complexity': "Unknown",
                'impact': "Unknown"
            }

    def _format_file_changes(self, file_changes) -> str:
        return "\n".join([
            f"- {f['filename']}: +{f['additions']}, -{f['deletions']}, {f['status']}"
            for f in file_changes[:5]  # Limit to first 5 files
        ])

    def _format_commits(self, commits) -> str:
        return "\n".join([
            f"- {c['message']}"
            for c in commits[:5]  # Limit to first 5 commits
        ])

    def _assess_complexity(self, file_changes) -> str:
        total_changes = sum(f['additions'] + f['deletions'] for f in file_changes)
        if total_changes < 50:
            return "Low"
        elif total_changes < 200:
            return "Medium"
        else:
            return "High"

    def _assess_impact(self, file_changes, commits) -> str:
        # Simple impact assessment based on number of files and commits
        if len(file_changes) < 3 and len(commits) < 3:
            return "Low"
        elif len(file_changes) < 10 and len(commits) < 10:
            return "Medium"
        else:
            return "High"