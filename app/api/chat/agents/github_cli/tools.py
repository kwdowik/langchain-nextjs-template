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

# class GitHubCLIBaseTool(BaseTool):
#     """Base class for GitHub CLI tools."""
    
#     def _run_gh_command(self, command: str) -> Dict[Any, Any]:
#         """Run a GitHub CLI command and return the JSON output."""
#         try:
#             # Add 'gh' prefix and ensure JSON output
#             if not command.startswith('gh '):
#                 command = f'gh {command}'
            
#             result = subprocess.run(
#                 command,
#                 shell=True,
#                 capture_output=True,
#                 text=True
#             )
            
#             if result.returncode != 0:
#                 raise Exception(f"Command failed: {result.stderr}")
                
#             return json.loads(result.stdout)
#         except json.JSONDecodeError:
#             raise Exception(f"Failed to parse JSON output: {result.stdout}")
#         except Exception as e:
#             raise Exception(f"Error running command: {str(e)}")

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
            # Request more fields in the JSON output for better verification
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
    description: str = "Gets contribution statistics for a user in a Chili-Piper repository for a specific time period"
    args_schema: type[GetUserContributionsArgs] = GetUserContributionsArgs
    
    def _run(self, author: str, repo: str, since: str, until: str) -> str:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d").isoformat()
            until_date = datetime.strptime(until, "%Y-%m-%d").isoformat()
            
            command = f'gh api -H "Accept: application/vnd.github+json" /repos/Chili-Piper/{repo}/commits?author={author}&since={since_date}&until={until_date}'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            logger.info(f"Executing GitHub CLI command: {command}")
            
            if result.returncode != 0:
                return json.dumps({
                    "error": f"Failed to get contributions: {result.stderr.strip()}",
                    "command": command
                })
            
            try:
                json_data = json.loads(result.stdout)
                return json.dumps({
                    "success": True,
                    "data": json_data,
                    "count": len(json_data)
                })
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Failed to parse GitHub API output as JSON",
                    "raw_output": result.stdout
                })
                
        except ValueError as e:
            return json.dumps({
                "error": "Dates must be in YYYY-MM-DD format",
                "details": str(e)
            })
        except Exception as e:
            return json.dumps({
                "error": f"Error getting contributions: {str(e)}",
                "command": command
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