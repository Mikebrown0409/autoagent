"""Main orchestrator loop for the autonomous two-agent coding system."""

import os
import time
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    CONTROL_FILE,
    INSTRUCTIONS_FILE,
    TASK_FILE,
    MEMORY_FILE,
    LOG_FILE,
    SLEEP_SECONDS,
    GIT_AUTO_COMMIT,
)
from agents import GrokClient, PlannerAgent, CoderAgent, get_repo_summary


def read_file_safe(filepath: str, default: str = "") -> str:
    """Read a file, returning default if it doesn't exist."""
    path = Path(filepath)
    if path.exists():
        return path.read_text()
    return default


def write_file_safe(filepath: str, content: str) -> None:
    """Write content to a file, creating directories if needed."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def get_control_state() -> str:
    """Read the control file and return RUN or PAUSE."""
    content = read_file_safe(CONTROL_FILE, "RUN").strip().upper()
    return content if content in ["RUN", "PAUSE"] else "RUN"


def apply_coder_changes(coder_output: str) -> dict:
    """
    Parse coder output and apply file changes.
    
    Expected format:
    - Code blocks with file paths: ```python:path/to/file.py
    - Commands to execute: <!-- EXECUTE: command -->
    
    Returns dict with:
    - files_modified: list of file paths
    - commands_run: list of commands executed
    - summary: text summary
    """
    files_modified = []
    commands_run = []
    
    # Extract file modifications from code blocks with file paths
    # Pattern: ```language:path/to/file or ```:path/to/file
    file_pattern = r"```(?:\w+)?:([^\n\s]+)\n(.*?)```"
    matches = re.findall(file_pattern, coder_output, re.DOTALL)
    
    for filepath, content in matches:
        filepath = filepath.strip()
        if filepath:
            try:
                write_file_safe(filepath, content.strip())
                files_modified.append(filepath)
            except Exception as e:
                print(f"Error writing {filepath}: {e}")
    
    # Extract and execute commands
    # Pattern: <!-- EXECUTE: command -->
    command_pattern = r"<!--\s*EXECUTE:\s*(.+?)\s*-->"
    command_matches = re.findall(command_pattern, coder_output, re.IGNORECASE)
    
    for command in command_matches:
        command = command.strip()
        if command:
            try:
                print(f"Executing: {command}")
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
                commands_run.append({
                    "command": command,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                })
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            except subprocess.TimeoutExpired:
                print(f"Command timed out: {command}")
            except Exception as e:
                print(f"Error executing command: {e}")
    
    # Extract summary (everything that's not a code block or command)
    summary = coder_output
    # Remove code blocks
    summary = re.sub(r"```.*?```", "", summary, flags=re.DOTALL)
    # Remove command markers
    summary = re.sub(r"<!--\s*EXECUTE:.*?-->", "", summary, flags=re.IGNORECASE | re.DOTALL)
    summary = summary.strip()
    
    return {
        "files_modified": files_modified,
        "commands_run": commands_run,
        "summary": summary,
    }


def git_diff() -> str:
    """Get git diff of current changes."""
    try:
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout
    except Exception:
        return ""


def git_commit(message: str) -> bool:
    """Commit changes with the given message."""
    try:
        # Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        if not status_result.stdout.strip():
            return False  # No changes to commit
        
        # Add all changes
        subprocess.run(
            ["git", "add", "-A"],
            check=True,
            capture_output=True,
        )
        
        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
        )
        return True
    except Exception as e:
        print(f"Error committing: {e}")
        return False


def update_memory(planner_output: str, coder_output: str, changes: dict) -> None:
    """Update memory.md with recent progress."""
    memory = read_file_safe(MEMORY_FILE, "")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"""## {timestamp}

### Tasks Generated:
{planner_output[:500]}...

### Implementation Summary:
{changes['summary'][:500]}...

### Files Modified:
{', '.join(changes['files_modified']) if changes['files_modified'] else 'None'}

### Commands Executed:
{len(changes['commands_run'])} command(s)

---

"""
    
    # Keep only last 10 entries (roughly)
    entries = memory.split("---\n\n")
    entries = [e for e in entries if e.strip()]
    entries.insert(0, entry)
    entries = entries[:10]
    
    new_memory = "\n\n---\n\n".join(entries)
    write_file_safe(MEMORY_FILE, new_memory)


def update_log(planner_output: str, coder_output: str) -> None:
    """Update log.md with recent agent outputs."""
    log = read_file_safe(LOG_FILE, "")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"""## {timestamp}

### Planner Output:
{planner_output}

### Coder Output:
{coder_output}

---

"""
    
    # Keep only last 5 entries
    entries = log.split("---\n\n")
    entries = [e for e in entries if e.strip()]
    entries.insert(0, entry)
    entries = entries[:5]
    
    new_log = "\n\n---\n\n".join(entries)
    write_file_safe(LOG_FILE, new_log)


def main_loop():
    """Main orchestrator loop."""
    print("Starting autonomous two-agent coding system...")
    print(f"Control file: {CONTROL_FILE}")
    print(f"Instructions file: {INSTRUCTIONS_FILE}")
    print("Press Ctrl+C to stop\n")
    
    # Initialize agents
    try:
        client = GrokClient()
        planner = PlannerAgent(client)
        coder = CoderAgent(client)
    except Exception as e:
        print(f"Error initializing agents: {e}")
        print("Make sure XAI_API_KEY environment variable is set.")
        return
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            # 1. Check control state
            control_state = get_control_state()
            if control_state == "PAUSE":
                print("System is PAUSED. Waiting...")
                time.sleep(SLEEP_SECONDS)
                continue
            
            print("System is RUNNING.")
            
            # 2. Read instructions
            instructions = read_file_safe(INSTRUCTIONS_FILE, "")
            if not instructions.strip():
                print("No instructions found. Waiting...")
                time.sleep(SLEEP_SECONDS)
                continue
            
            # 3. Read memory
            memory = read_file_safe(MEMORY_FILE, "")
            
            # 4. Get repo summary
            repo_summary = get_repo_summary()
            
            # 5. Planner Agent
            print("\n[Planner Agent] Generating tasks...")
            try:
                planner_output = planner.generate_tasks(instructions, memory, repo_summary)
                write_file_safe(TASK_FILE, planner_output)
                print("Tasks generated and written to task.md")
            except Exception as e:
                print(f"Error in Planner Agent: {e}")
                time.sleep(SLEEP_SECONDS)
                continue
            
            # 6. Coder Agent
            print("\n[Coder Agent] Implementing tasks...")
            try:
                task = read_file_safe(TASK_FILE, "")
                coder_output = coder.implement_task(task, memory, repo_summary)
                
                # Apply changes
                changes = apply_coder_changes(coder_output)
                print(f"\nFiles modified: {len(changes['files_modified'])}")
                print(f"Commands executed: {len(changes['commands_run'])}")
                
            except Exception as e:
                print(f"Error in Coder Agent: {e}")
                coder_output = f"Error: {str(e)}"
                changes = {"files_modified": [], "commands_run": [], "summary": coder_output}
            
            # 7. Git safety
            if GIT_AUTO_COMMIT and changes["files_modified"]:
                print("\n[Git] Showing diff...")
                diff = git_diff()
                if diff:
                    print(diff[:1000] + "..." if len(diff) > 1000 else diff)
                
                commit_message = f"Auto-commit: {changes['summary'][:100]}"
                if git_commit(commit_message):
                    print(f"Changes committed: {commit_message}")
                else:
                    print("No changes to commit or commit failed")
            
            # 8. Update memory and log
            update_memory(planner_output, coder_output, changes)
            update_log(planner_output, coder_output)
            
            # 9. Sleep before next iteration
            print(f"\nSleeping for {SLEEP_SECONDS} seconds...")
            time.sleep(SLEEP_SECONDS)
    
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main_loop()

