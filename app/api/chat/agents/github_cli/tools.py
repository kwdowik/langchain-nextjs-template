from typing import Optional, List, Dict, Any
from langchain.tools import BaseTool
import json
import subprocess
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ListPullRequestsArgs(BaseModel):
    author: str = Field(description="The GitHub username of the PR author")
    repo: str = Field(default="frontend", description="The repository name (default: frontend)")
    state: str = Field(default="all", description="PR state (open, closed, merged, all)")
    limit: int = Field(default=20, description="Maximum number of PRs to return")

    model_config = {
        "populate_by_name": True
    }

class GetPRDetailsArgs(BaseModel):
    repo: str = Field(description="The repository name")
    pr_number: int = Field(description="The PR number to get details for")

    model_config = {
        "populate_by_name": True
    }

class GetUserContributionsArgs(BaseModel):
    author: str = Field(description="The GitHub username to get contributions for")
    repo: str = Field(description="The repository name")
    since: str = Field(description="Start date in YYYY-MM-DD format")
    until: str = Field(description="End date in YYYY-MM-DD format")

    model_config = {
        "populate_by_name": True
    }

class AnalyzePRComplexityArgs(BaseModel):
    repo: str = Field(description="The repository name")
    pr_number: int = Field(description="The PR number to analyze")

    model_config = {
        "populate_by_name": True
    }

class ListPullRequests(BaseTool):
    name: str = "list_pull_requests"
    description: str = "Lists pull requests from a specific author in a Chili-Piper repository. Use this when asked to show PRs by a specific user."
    args_schema: type[ListPullRequestsArgs] = ListPullRequestsArgs
    
    def _run(self, author: str, repo: str = "frontend", state: str = "all", limit: int = 20) -> str:
        """Lists pull requests from a specific author."""
        logger.info(f"ListPullRequests tool called with args: author={author}, repo={repo}, state={state}, limit={limit}")
        try:
            # Request fields needed for PR complexity analysis
            command = f'gh pr list -R Chili-Piper/{repo} --author {author} --state {state} --limit {limit} --json number,title,state,createdAt,mergedAt,url,author'
            logger.info(f"Executing GitHub CLI command: {command}")
            
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            logger.info(f"Command exit code: {result.returncode}")
            logger.info(f"Command stdout: {result.stdout}")
            logger.info(f"Command stderr: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"GitHub CLI command failed: {error_msg}")
                return json.dumps({
                    "error": f"Failed to list PRs: {error_msg}",
                    "command": command
                })
            
            try:
                json_data = json.loads(result.stdout)
                logger.info(f"Successfully parsed JSON data with {len(json_data)} PRs")
                
                # Format the data to include clear verification information
                formatted_prs = []
                for pr in json_data:
                    formatted_pr = {
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "url": pr.get("url"),
                        "created_at": pr.get("createdAt"),
                        "merged_at": pr.get("mergedAt"),
                        "author": pr.get("author", {}).get("login"),
                        "repository": f"Chili-Piper/{repo}"
                    }
                    formatted_prs.append(formatted_pr)
                    logger.info(f"Formatted PR: #{formatted_pr['number']} - {formatted_pr['title']}")
                
                response = json.dumps({
                    "success": True,
                    "data": formatted_prs,
                    "count": len(formatted_prs),
                    "verification_note": "You can verify these PRs by visiting the provided URLs"
                }, indent=2)
                logger.info("Successfully prepared response")
                return response
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON output: {e}")
                return json.dumps({
                    "error": "Failed to parse GitHub CLI output as JSON",
                    "raw_output": result.stdout
                })
                
        except Exception as e:
            logger.error(f"Error executing GitHub CLI command: {str(e)}")
            return json.dumps({
                "error": f"Error listing PRs: {str(e)}",
                "command": command
            })

class GetPRDetails(BaseTool):
    name: str = "get_pr_details"
    description: str = "Gets detailed information about a specific PR in a Chili-Piper repository"
    args_schema: type[GetPRDetailsArgs] = GetPRDetailsArgs
    
    def _run(self, repo: str, pr_number: int) -> str:
        try:
            command = f'gh pr view {pr_number} -R Chili-Piper/{repo} --json number,title,state,body,additions,deletions,changedFiles,files,commits'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            logger.info(f"Executing GitHub CLI command: {command}")
            
            if result.returncode != 0:
                return json.dumps({
                    "error": f"Failed to get PR details: {result.stderr.strip()}",
                    "command": command
                })
            
            try:
                json_data = json.loads(result.stdout)
                return json.dumps({
                    "success": True,
                    "data": json_data
                })
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Failed to parse GitHub CLI output as JSON",
                    "raw_output": result.stdout
                })
                
        except Exception as e:
            return json.dumps({
                "error": f"Error getting PR details: {str(e)}",
                "command": command
            })

class GetUserContributions(BaseTool):
    name: str = "get_user_contributions"
    description: str = "Gets comprehensive contribution statistics (commits and PRs) for a user in a Chili-Piper repository for a specific time period"
    args_schema: type[GetUserContributionsArgs] = GetUserContributionsArgs
    
    def _validate_github_response(self, result: subprocess.CompletedProcess, context: str) -> tuple[bool, Optional[Any], Optional[str]]:
        """Validates GitHub CLI response and returns (is_valid, parsed_data, error_message)"""
        if result.returncode != 0:
            return False, None, f"GitHub CLI {context} failed: {result.stderr.strip()}"
            
        try:
            if not result.stdout.strip():
                return False, None, f"No {context} data returned"
                
            data = json.loads(result.stdout)
            if not isinstance(data, (list, dict)):
                return False, None, f"Invalid {context} data format"
                
            return True, data, None
        except json.JSONDecodeError:
            return False, None, f"Failed to parse {context} JSON data"
    
    def _run(self, author: str, repo: str, since: str, until: str) -> str:
        try:
            # Validate date formats first
            try:
                since_date = datetime.strptime(since, "%Y-%m-%d").isoformat()
                until_date = datetime.strptime(until, "%Y-%m-%d").isoformat()
            except ValueError as e:
                return json.dumps({
                    "error": "Invalid date format. Please use YYYY-MM-DD format.",
                    "details": str(e)
                })

            # Initialize response structure
            response = {
                "success": False,
                "date_range": {"since": since, "until": until},
                "commits": {"total": 0, "sample": [], "error": None},
                "pull_requests": {
                    "total": 0,
                    "sample": [],
                    "states": {"open": 0, "closed": 0, "merged": 0},
                    "error": None
                }
            }

            # Get commits
            commits_command = f'gh api -H "Accept: application/vnd.github+json" /repos/Chili-Piper/{repo}/commits?author={author}&since={since_date}&until={until_date}'
            commits_result = subprocess.run(commits_command, shell=True, capture_output=True, text=True)
            logger.info(f"Executing GitHub CLI command for commits: {commits_command}")
            
            is_valid, commits_data, error = self._validate_github_response(commits_result, "commits")
            if is_valid and commits_data:
                response["commits"]["total"] = len(commits_data)
                for commit in commits_data[:5]:  # Only process first 5 commits
                    if not isinstance(commit, dict):
                        continue
                        
                    commit_data = commit.get("commit", {})
                    if not isinstance(commit_data, dict):
                        continue
                        
                    commit_info = {
                        "sha": commit.get("sha", "")[:8] if commit.get("sha") else "unknown",
                        "date": commit_data.get("author", {}).get("date", "unknown"),
                        "message": (commit_data.get("message", "").split("\n")[0] 
                                  if commit_data.get("message") else "No message")
                    }
                    response["commits"]["sample"].append(commit_info)
            else:
                response["commits"]["error"] = error

            # Get PRs
            prs_command = f'gh pr list -R Chili-Piper/{repo} --author {author} --json number,title,state,createdAt,mergedAt,url --search "created:{since}..{until}"'
            prs_result = subprocess.run(prs_command, shell=True, capture_output=True, text=True)
            logger.info(f"Executing GitHub CLI command for PRs: {prs_command}")
            
            is_valid, prs_data, error = self._validate_github_response(prs_result, "pull requests")
            if is_valid and prs_data:
                response["pull_requests"]["total"] = len(prs_data)
                
                # Count PR states with validation
                for pr in prs_data:
                    if not isinstance(pr, dict):
                        continue
                        
                    state = pr.get("state", "").lower()
                    if state == "open":
                        response["pull_requests"]["states"]["open"] += 1
                    elif state == "closed":
                        if pr.get("mergedAt"):
                            response["pull_requests"]["states"]["merged"] += 1
                        else:
                            response["pull_requests"]["states"]["closed"] += 1
                
                # Process PR samples with validation
                for pr in prs_data[:5]:  # Only process first 5 PRs
                    if not isinstance(pr, dict):
                        continue
                        
                    pr_info = {
                        "number": pr.get("number", "unknown"),
                        "title": pr.get("title", "No title"),
                        "state": pr.get("state", "unknown"),
                        "created_at": pr.get("createdAt", "unknown"),
                        "merged_at": pr.get("mergedAt"),
                        "url": pr.get("url", "unknown")
                    }
                    response["pull_requests"]["sample"].append(pr_info)
            else:
                response["pull_requests"]["error"] = error

            # Set success based on whether we got any valid data
            response["success"] = (
                response["commits"]["total"] > 0 or 
                response["pull_requests"]["total"] > 0 or 
                (response["commits"]["error"] is None and response["pull_requests"]["error"] is None)
            )

            return json.dumps(response, indent=2)
                
        except Exception as e:
            logger.error(f"Error in GetUserContributions: {str(e)}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            })

class AnalyzePRComplexity(BaseTool):
    name: str = "analyze_pr_complexity"
    description: str = "Analyzes PR complexity in a Chili-Piper repository based on number of files, lines changed, and file types"
    args_schema: type[AnalyzePRComplexityArgs] = AnalyzePRComplexityArgs
    
    def _run(self, repo: str, pr_number: int) -> str:
        try:
            command = f'gh pr view {pr_number} -R Chili-Piper/{repo} --json files,additions,deletions,changedFiles'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            logger.info(f"Executing GitHub CLI command: {command}")

            if result.returncode != 0:
                return json.dumps({
                    "error": f"Failed to get PR data: {result.stderr.strip()}",
                    "command": command
                })
            
            try:
                pr_data = json.loads(result.stdout)
                
                total_changes = pr_data.get('additions', 0) + pr_data.get('deletions', 0)
                files_changed = pr_data.get('changedFiles', 0)
                
                complexity = {
                    'level': 'LOW',
                    'reasons': []
                }
                
                if total_changes > 500:
                    complexity['level'] = 'HIGH'
                    complexity['reasons'].append(f'Large number of changes: {total_changes} lines')
                elif total_changes > 200:
                    complexity['level'] = 'MEDIUM'
                    complexity['reasons'].append(f'Moderate number of changes: {total_changes} lines')
                    
                if files_changed > 10:
                    complexity['level'] = 'HIGH'
                    complexity['reasons'].append(f'Many files changed: {files_changed} files')
                elif files_changed > 5:
                    if complexity['level'] != 'HIGH':
                        complexity['level'] = 'MEDIUM'
                    complexity['reasons'].append(f'Multiple files changed: {files_changed} files')
                    
                file_types = {}
                for file in pr_data.get('files', []):
                    ext = file['path'].split('.')[-1] if '.' in file['path'] else 'no_extension'
                    file_types[ext] = file_types.get(ext, 0) + 1
                    
                if len(file_types) > 3:
                    if complexity['level'] != 'HIGH':
                        complexity['level'] = 'MEDIUM'
                    complexity['reasons'].append(f'Multiple file types affected: {list(file_types.keys())}')
                    
                return json.dumps({
                    'success': True,
                    'complexity': complexity,
                    'statistics': {
                        'total_changes': total_changes,
                        'files_changed': files_changed,
                        'file_types': file_types
                    }
                }, indent=2)
                
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Failed to parse GitHub CLI output as JSON",
                    "raw_output": result.stdout
                })
                
        except Exception as e:
            return json.dumps({
                "error": f"Error analyzing PR complexity: {str(e)}",
                "command": command
            })

def get_github_cli_tools() -> List[BaseTool]:
    """Returns a list of all available GitHub CLI tools."""
    logger.info("Initializing GitHub CLI tools")
    return [
        ListPullRequests(),
        GetPRDetails(),
        GetUserContributions(),
        AnalyzePRComplexity()
    ] 