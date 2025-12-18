"""Main orchestrator loop for the autonomous two-agent coding system."""

import os
import sys
import time
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure unbuffered output for real-time visibility
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

from config import (
    CONTROL_FILE,
    INSTRUCTIONS_FILE,
    TASK_FILE,
    MEMORY_FILE,
    LOG_FILE,
    SLEEP_SECONDS,
    GIT_AUTO_COMMIT,
    WORKSPACE_DIR,
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
    
    # Get absolute paths
    workspace_path = Path(WORKSPACE_DIR).resolve()
    agent_path = Path(__file__).parent.resolve()
    
    # Extract file modifications from code blocks with file paths
    # Pattern: ```language:path/to/file or ```:path/to/file
    file_pattern = r"```(?:\w+)?:([^\n\s]+)\n(.*?)```"
    matches = re.findall(file_pattern, coder_output, re.DOTALL)
    
    for filepath, content in matches:
        filepath = filepath.strip()
        if filepath:
            # Resolve to absolute path in workspace
            if Path(filepath).is_absolute():
                target_path = Path(filepath)
            else:
                target_path = workspace_path / filepath
            
            # CRITICAL: Prevent writing to agent folder
            try:
                target_resolved = target_path.resolve()
                agent_resolved = agent_path.resolve()
                # Check if target is inside agent folder
                if str(target_resolved).startswith(str(agent_resolved)):
                    print(f"⚠️  BLOCKED: Attempted to modify file in agent folder: {filepath}")
                    print(f"   Agents should NOT modify files in the agent/ directory.")
                    print(f"   Protected files: log.md, memory.md, task.md, control.txt, instructions.md, and all agent/ files")
                    continue
            except Exception:
                pass  # If path resolution fails, continue with validation
            
            try:
                write_file_safe(str(target_path), content.strip())
                files_modified.append(str(target_path.relative_to(workspace_path)))
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
                workspace_path = Path(WORKSPACE_DIR).resolve()
                print(f"Executing: {command}")
                print(f"  (from workspace: {workspace_path})")
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(workspace_path),  # Run commands from workspace directory
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
    """Get git diff of current changes from workspace directory."""
    try:
        workspace_path = Path(WORKSPACE_DIR).resolve()
        result = subprocess.run(
            ["git", "diff"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout
    except Exception:
        return ""


def git_commit(message: str) -> bool:
    """Commit changes with the given message from workspace directory."""
    try:
        workspace_path = Path(WORKSPACE_DIR).resolve()
        
        # Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            check=True,
        )
        if not status_result.stdout.strip():
            return False  # No changes to commit
        
        # Add all changes (agent folder is protected by file writing logic)
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(workspace_path),
            check=True,
            capture_output=True,
        )
        
        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(workspace_path),
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


def get_user_query() -> str:
    """Get initial project query from user via command line or interactive prompt."""
    # Check command line arguments
    if len(sys.argv) > 1:
        # Query provided as command line argument
        query = " ".join(sys.argv[1:])
        print(f"📝 Project query from command line: {query}\n")
        return query
    
    # Interactive prompt
    print("="*60)
    print("Autonomous Two-Agent Coding System")
    print("="*60)
    print("\nEnter your project goal/query (or leave empty to use instructions.md):")
    print("Example: 'Build a REST API for a todo list'")
    print("Example: 'Create a web scraper for news articles'\n")
    
    query = input("> ").strip()
    
    if not query:
        # Fall back to instructions.md if it exists
        existing = read_file_safe(INSTRUCTIONS_FILE, "")
        if existing.strip():
            print(f"\nUsing existing instructions from {INSTRUCTIONS_FILE}")
            return existing.strip()
        else:
            print("\nNo query provided and no instructions.md found. Exiting.")
            sys.exit(1)
    
    return query


def get_initial_plan_and_confirmation(planner: PlannerAgent, query: str) -> str:
    """Get initial plan from Planner and confirm with user."""
    print("\n" + "="*60)
    print("[Planner Agent] Generating Initial Project Plan...")
    print("="*60)
    print("📤 Sending request to Planner Agent (this may take a moment)...")
    sys.stdout.flush()
    
    try:
        # Get initial plan (no previous work, empty memory)
        repo_summary = get_repo_summary()
        initial_plan = planner.generate_tasks(query, "", repo_summary, "")
        
        # Display the plan
        print("\n" + "="*60)
        print("📋 INITIAL PROJECT PLAN")
        print("="*60)
        print(initial_plan)
        print("="*60)
        
        # Get user confirmation
        print("\n🤔 Review the plan above.")
        print("Options:")
        print("  [y/yes] - Approve and start autonomous execution")
        print("  [n/no]  - Reject and exit")
        print("  [e/edit] - Edit the query and regenerate plan")
        print()
        
        while True:
            response = input("Approve this plan? (y/n/e): ").strip().lower()
            
            if response in ['y', 'yes']:
                print("\n✅ Plan approved! Starting autonomous execution...\n")
                return initial_plan
            elif response in ['n', 'no']:
                print("\n❌ Plan rejected. Exiting.")
                sys.exit(0)
            elif response in ['e', 'edit']:
                new_query = input("\nEnter revised project query: ").strip()
                if new_query:
                    return get_initial_plan_and_confirmation(planner, new_query)
                else:
                    print("Query cannot be empty. Try again.")
            else:
                print("Please enter 'y', 'n', or 'e'")
    
    except Exception as e:
        print(f"❌ Error generating initial plan: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main_loop():
    """Main orchestrator loop."""
    print("Starting autonomous two-agent coding system...")
    
    # Initialize agents
    try:
        client = GrokClient()
        planner = PlannerAgent(client)
        coder = CoderAgent(client)
    except Exception as e:
        print(f"Error initializing agents: {e}")
        print("Make sure XAI_API_KEY environment variable is set.")
        return
    
    # Get initial query and plan
    query = get_user_query()
    confirmed_plan = get_initial_plan_and_confirmation(planner, query)
    
    # Save confirmed plan to instructions.md
    write_file_safe(INSTRUCTIONS_FILE, query)
    write_file_safe(TASK_FILE, confirmed_plan)
    
    print(f"💾 Saved project query to {INSTRUCTIONS_FILE}")
    print(f"💾 Saved initial plan to {TASK_FILE}")
    print(f"\n📁 Control file: {CONTROL_FILE} (set to PAUSE to stop)")
    print("Press Ctrl+C to stop\n")
    print("="*60)
    print("🚀 AUTONOMOUS EXECUTION STARTED")
    print("="*60 + "\n")
    
    iteration = 0
    last_coder_summary = ""  # Track what Coder completed last iteration
    
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
            
            # 2. Read instructions (project goal)
            instructions = read_file_safe(INSTRUCTIONS_FILE, "")
            if not instructions.strip():
                print("⚠️  No project goal found. Exiting.")
                break
            
            # 3. Read memory
            memory = read_file_safe(MEMORY_FILE, "")
            
            # 4. Get repo summary
            repo_summary = get_repo_summary()
            
            # 5. Planner Agent (with feedback from last Coder work)
            print("\n" + "="*60)
            print("[Planner Agent] Strategic Planning...")
            print("="*60)
            if last_coder_summary:
                print("📋 Reviewing Coder's previous work and planning next steps...")
            else:
                print("📋 Starting new project - planning initial steps...")
            print("📤 Sending request to Planner Agent (this may take a moment)...")
            sys.stdout.flush()
            try:
                planner_output = planner.generate_tasks(instructions, memory, repo_summary, last_coder_summary)
                write_file_safe(TASK_FILE, planner_output)
                print("✓ Tasks generated and written to task.md")
                print(f"\n📋 Generated Tasks Preview:\n{'-'*60}")
                print(planner_output[:500])
                if len(planner_output) > 500:
                    print("...")
                print("-"*60 + "\n")
                sys.stdout.flush()
            except Exception as e:
                print(f"❌ Error in Planner Agent: {e}")
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                time.sleep(SLEEP_SECONDS)
                continue
            
            # 6. Coder Agent
            print("\n" + "="*60)
            print("[Coder Agent] Implementing tasks...")
            print("="*60)
            print("📤 Sending request to Coder Agent (this may take a moment)...")
            sys.stdout.flush()
            try:
                task = read_file_safe(TASK_FILE, "")
                coder_output = coder.implement_task(task, memory, repo_summary)
                print("✓ Coder Agent response received")
                print(f"\n💻 Coder Output Preview:\n{'-'*60}")
                print(coder_output[:800])
                if len(coder_output) > 800:
                    print("...")
                print("-"*60 + "\n")
                sys.stdout.flush()
                
                # Apply changes
                print("\n[Orchestrator] Parsing and applying changes...")
                changes = apply_coder_changes(coder_output)
                print(f"✓ Files modified: {len(changes['files_modified'])}")
                if changes['files_modified']:
                    for f in changes['files_modified']:
                        print(f"  - {f}")
                print(f"✓ Commands executed: {len(changes['commands_run'])}")
                if changes['commands_run']:
                    for cmd in changes['commands_run']:
                        print(f"  - {cmd['command']}")
                
                # Store Coder's summary for next Planner iteration
                last_coder_summary = changes['summary']
                print(f"\n💬 Coder Summary (will be reviewed by Planner next iteration):")
                print(f"   {last_coder_summary[:200]}...")
                
            except Exception as e:
                print(f"Error in Coder Agent: {e}")
                coder_output = f"Error: {str(e)}"
                changes = {"files_modified": [], "commands_run": [], "summary": coder_output}
                last_coder_summary = changes['summary']
            
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

