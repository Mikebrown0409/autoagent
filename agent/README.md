# Autonomous Two-Agent Coding Orchestrator

A minimal autonomous two-agent coding system in Python that runs unattended but allows human supervision and control.

## Overview

This system uses two specialized agents:

1. **Planner Agent** (`grok-4-1-fast-non-reasoning`): Generates structured coding tasks from high-level instructions
2. **Coder Agent** (`grok-code-fast-1`): Implements tasks by modifying files and running commands

The system operates in a continuous loop, reading instructions, generating tasks, implementing them, and committing changes to git.

## Features

- **Autonomous Operation**: Runs continuously without human intervention
- **Human Control**: Pause/resume via `control.txt`, modify goals via `instructions.md`
- **Git Safety**: Automatic commits with diffs, easy rollback
- **Simple & Readable**: Minimal codebase, clear structure

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set your xAI API key:**
   
   Option 1: Create a `.env` file in the `agent` directory (recommended):
   ```bash
   echo "XAI_API_KEY=your-api-key-here" > .env
   ```
   
   Option 2: Export as environment variable:
   ```bash
   export XAI_API_KEY="your-api-key-here"
   ```

3. **Initialize git repository (if not already):**
   ```bash
   git init
   ```

4. **Optional: Pre-configure (or let the system prompt you):**
   - You can edit `instructions.md` with your goals, OR
   - The system will prompt you for a project query when you run it
   - Set `control.txt` to `RUN` or `PAUSE` (defaults to RUN)

5. **Run the orchestrator:**
   
   Option 1: Provide query as command line argument:
   ```bash
   cd agent
   python main.py "Build a REST API for a todo list"
   ```
   
   Option 2: Interactive prompt:
   ```bash
   cd agent
   python main.py
   # Then enter your project query when prompted
   ```
   
   The Planner will generate an initial plan, show it to you for approval, then start autonomous execution.

## File Structure

```
.
└── agent/
    ├── main.py           # Orchestrator loop
    ├── agents.py         # Planner + Coder agent logic
    ├── prompts.py        # System prompts
    ├── config.py        # Model names, token limits
    ├── instructions.md   # Project goal (auto-set from initial query, can be edited)
    ├── task.md           # Planner output (auto-generated)
    ├── memory.md         # Rolling summary of progress (auto-generated)
    ├── control.txt       # RUN or PAUSE (EDIT THIS)
    ├── log.md            # Recent agent outputs (auto-generated)
    └── README.md
```

## Human Control

### Pause/Resume

Edit `control.txt`:
- `RUN` - System continues operating
- `PAUSE` - System sleeps and waits

### Change Goals

Edit `instructions.md` with your new goals. The Planner Agent will read this on the next iteration.

### Inspect Progress

- `memory.md` - Summary of recent work
- `log.md` - Full agent outputs
- `task.md` - Current task list
- `git log` - Commit history
- `git diff` - See changes before they're committed

### Rollback

Use standard git commands:
```bash
git log                    # View commit history
git show <commit-hash>     # View specific commit
git reset --hard <commit>  # Rollback to specific commit
```

## How It Works

### Initial Setup
1. **Start System**: Run `python main.py` with a project query (or enter interactively)
2. **Planner Generates Plan**: Planner Agent creates initial strategic plan
3. **User Confirmation**: Review and approve the plan (y/n/e to edit)
4. **Autonomous Execution**: Once approved, system runs autonomously

### Main Loop
1. **Read Control**: Checks `control.txt` for RUN/PAUSE
2. **Read Project Goal**: Loads goal from `instructions.md` (set during initial setup)
3. **Planner Agent**: Reviews Coder's work, plans next strategic steps → `task.md`
4. **Coder Agent**: Implements tasks → modifies files
5. **Git Commit**: Shows diff, commits with descriptive message
6. **Update Memory**: Records progress in `memory.md`
7. **Repeat**: Planner reviews progress and plans next steps

## Coder Agent Output Format

The Coder Agent outputs structured markdown:

- **File modifications**: Code blocks with file paths
  ```
  ```python:path/to/file.py
  # code content
  ```
  ```

- **Commands to execute**: HTML comments
  ```
  <!-- EXECUTE: python -m pytest -->
  ```

## Configuration

Edit `config.py` to adjust:
- Model names
- Token limits
- Sleep duration
- Auto-commit behavior

## Safety Features

- Git commits after each cycle (if changes made)
- Diffs shown before committing
- Never force-pushes or amends
- Human can pause at any time
- All changes tracked in git history

## Troubleshooting

**"XAI_API_KEY environment variable not set"**
- Create a `.env` file in the `agent` directory with: `XAI_API_KEY=your-key`
- Or set the environment variable: `export XAI_API_KEY="your-key"`

**System not making changes**
- Check `control.txt` is set to `RUN`
- Check `instructions.md` has content
- Check `log.md` for agent errors

**Want to stop the system**
- Press `Ctrl+C` or set `control.txt` to `PAUSE`

## License

MIT
