"""Agent implementations for Planner and Coder."""

import os
import subprocess
from pathlib import Path
from typing import Optional
from config import PLANNER_MODEL, CODER_MODEL, PLANNER_MAX_TOKENS, CODER_MAX_TOKENS, WORKSPACE_DIR
from prompts import (
    PLANNER_SYSTEM_PROMPT,
    CODER_SYSTEM_PROMPT,
    get_planner_prompt,
    get_coder_prompt,
)

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Load .env from the agent directory or parent directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try parent directory
        parent_env = Path(__file__).parent.parent / ".env"
        if parent_env.exists():
            load_dotenv(parent_env)
        else:
            # Try current working directory
            load_dotenv()
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass


class GrokClient:
    """Client for interacting with xAI Grok API."""
    
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable not set. Set it in .env file or export XAI_API_KEY")
    
    def call_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> str:
        """
        Call the Grok API with the given parameters.
        
        This implementation uses the xAI Python SDK if available,
        otherwise falls back to HTTP requests.
        """
        try:
            # Try using xAI SDK first
            import xai
            client = xai.Client(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
            )
            # Log token usage if available
            if hasattr(response, 'usage'):
                usage = response.usage
                print(f"  📊 Token usage: {usage.prompt_tokens} prompt + {usage.completion_tokens} completion = {usage.total_tokens} total")
            return response.choices[0].message.content
        except ImportError:
            # Fallback to HTTP requests
            import requests
            
            url = "https://api.x.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            # Log token usage if available
            if "usage" in result:
                usage = result["usage"]
                print(f"  📊 Token usage: {usage.get('prompt_tokens', 0)} prompt + {usage.get('completion_tokens', 0)} completion = {usage.get('total_tokens', 0)} total")
            return result["choices"][0]["message"]["content"]


class PlannerAgent:
    """Planner Agent: Generates coding tasks from instructions."""
    
    def __init__(self, client: GrokClient):
        self.client = client
    
    def generate_tasks(
        self, instructions: str, memory: str, repo_summary: str
    ) -> str:
        """Generate a task list from instructions and context."""
        prompt = get_planner_prompt(instructions, memory, repo_summary)
        
        try:
            response = self.client.call_model(
                model=PLANNER_MODEL,
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=PLANNER_MAX_TOKENS,
            )
            return response.strip()
        except Exception as e:
            return f"# Error generating tasks\n\nError: {str(e)}\n\nPlease check your API key and network connection."


class CoderAgent:
    """Coder Agent: Implements tasks by modifying the repository."""
    
    def __init__(self, client: GrokClient):
        self.client = client
    
    def implement_task(
        self, task: str, memory: str, repo_summary: str
    ) -> str:
        """Implement the given task and return a summary."""
        prompt = get_coder_prompt(task, memory, repo_summary)
        
        try:
            response = self.client.call_model(
                model=CODER_MODEL,
                system_prompt=CODER_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=CODER_MAX_TOKENS,
            )
            return response.strip()
        except Exception as e:
            return f"Error implementing task: {str(e)}\n\nPlease check your API key and network connection."


def get_repo_summary() -> str:
    """Get a summary of the current repository state from the workspace directory."""
    try:
        workspace_path = Path(WORKSPACE_DIR).resolve()
        
        # Get list of files (excluding agent folder)
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            check=False,
        )
        files = result.stdout.strip().split("\n") if result.stdout else []
        # Filter out agent folder files
        files = [f for f in files if not f.startswith("agent/")]
        
        # Get recent git log
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            check=False,
        )
        recent_commits = log_result.stdout.strip() if log_result.stdout else "No commits yet"
        
        # Get git status
        status_result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            check=False,
        )
        status = status_result.stdout.strip() if status_result.stdout else "Working tree clean"
        
        summary = f"""Workspace directory: {workspace_path}
Files in repository (excluding agent/): {len(files)} files
Recent commits:
{recent_commits}

Git status:
{status}
"""
        return summary
    except Exception as e:
        return f"Error getting repo summary: {str(e)}"

