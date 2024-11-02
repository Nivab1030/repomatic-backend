import os
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from dotenv import load_dotenv
import asyncio
from tqdm.asyncio import tqdm_asyncio

class GitHubCollector:
    def __init__(self, repo_name: str = None, github_token: str = None):
        """Initialize the GitHub collector with repo name and token"""
        self.repo_name = repo_name or os.getenv('REPO_NAME')
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        
        if not self.repo_name or not self.github_token:
            raise ValueError("Repository name and GitHub token are required")
        
        self.base_url = "https://api.github.com"
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

    async def get_session(self):
        """Create and return an aiohttp session"""
        return aiohttp.ClientSession(headers=self.headers)

    async def async_fetch_pulls(self, session: aiohttp.ClientSession, days_back: int, max_items: int = 30) -> List[Dict]:
        """Fetch pull requests from the last N days"""
        since_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        url = f"{self.base_url}/repos/{self.repo_name}/pulls"
        params = {
            'state': 'all',
            'per_page': max_items,
            'sort': 'updated',
            'direction': 'desc'
        }

        async with session.get(url, params=params) as response:
            pulls = await response.json()
            
            processed_pulls = []
            async for pull in tqdm_asyncio(pulls, desc="Processing PRs"):
                created_at = datetime.fromisoformat(pull['created_at'].replace('Z', '+00:00'))
                if created_at >= since_date:
                    processed_pulls.append({
                        'number': pull['number'],
                        'title': pull['title'],
                        'body': pull['body'],
                        'state': pull['state'],
                        'created_at': pull['created_at'],
                        'updated_at': pull['updated_at'],
                        'merged_at': pull.get('merged_at'),
                        'url': pull['html_url'],
                        'author': pull['user']['login']
                    })
                if len(processed_pulls) >= max_items:
                    break
            
            return processed_pulls

    async def async_fetch_commits(self, session: aiohttp.ClientSession, days_back: int, max_items: int = 30) -> List[Dict]:
        """Fetch commits from the last N days"""
        since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        url = f"{self.base_url}/repos/{self.repo_name}/commits"
        params = {
            'since': since_date,
            'per_page': max_items
        }

        async with session.get(url, params=params) as response:
            commits = await response.json()
            
            processed_commits = []
            async for commit in tqdm_asyncio(commits[:max_items], desc="Processing commits"):
                processed_commits.append({
                    'sha': commit['sha'],
                    'message': commit['commit']['message'],
                    'date': commit['commit']['author']['date'],
                    'author': commit['commit']['author']['name'],
                    'url': commit['html_url']
                })
            
            return processed_commits

    async def async_fetch_issues(self, session: aiohttp.ClientSession, days_back: int, max_items: int = 30) -> List[Dict]:
        """Fetch issues from the last N days"""
        since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        url = f"{self.base_url}/repos/{self.repo_name}/issues"
        params = {
            'state': 'all',
            'since': since_date,
            'per_page': max_items
        }

        async with session.get(url, params=params) as response:
            issues = await response.json()
            
            processed_issues = []
            async for issue in tqdm_asyncio(issues, desc="Processing issues"):
                # Skip pull requests
                if 'pull_request' not in issue:
                    processed_issues.append({
                        'number': issue['number'],
                        'title': issue['title'],
                        'body': issue['body'],
                        'state': issue['state'],
                        'created_at': issue['created_at'],
                        'updated_at': issue['updated_at'],
                        'closed_at': issue.get('closed_at'),
                        'url': issue['html_url'],
                        'author': issue['user']['login']
                    })
                if len(processed_issues) >= max_items:
                    break
            
            return processed_issues
