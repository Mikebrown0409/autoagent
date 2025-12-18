"""Configuration for the autonomous two-agent coding system."""

import os

# Model configurations
PLANNER_MODEL = "grok-4-1-fast-non-reasoning"
CODER_MODEL = "grok-code-fast-1"

# Token limits
PLANNER_MAX_TOKENS = 2000
CODER_MAX_TOKENS = 8000

# Workspace directory (where agents will modify files)
# Set to parent directory by default - agents should NOT modify files in the agent/ folder
WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "..")

# File paths (relative to agent directory for control files)
CONTROL_FILE = "control.txt"
INSTRUCTIONS_FILE = "instructions.md"
TASK_FILE = "task.md"
MEMORY_FILE = "memory.md"
LOG_FILE = "log.md"

# Loop settings
SLEEP_SECONDS = 5  # Sleep between loop iterations when paused or after cycle

# Git settings
GIT_AUTO_COMMIT = True  # Automatically commit changes after coder agent runs

