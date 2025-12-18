#!/usr/bin/env python3
# Note: Use 'python3' command, not 'python'
"""Quick status check for the autonomous agent system."""

import subprocess
import sys
from pathlib import Path

def check_status():
    """Check if the system is running and show status."""
    # Check for running processes
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )
        processes = [line for line in result.stdout.split('\n') if 'main.py' in line and 'grep' not in line]
        
        if processes:
            print("🟢 SYSTEM IS RUNNING")
            print(f"   Found {len(processes)} process(es):")
            for proc in processes:
                parts = proc.split()
                if len(parts) > 1:
                    pid = parts[1]
                    print(f"   - PID: {pid}")
        else:
            print("🔴 SYSTEM IS NOT RUNNING")
    except Exception as e:
        print(f"Error checking processes: {e}")
    
    # Check control file
    control_file = Path(__file__).parent / "control.txt"
    if control_file.exists():
        control_state = control_file.read_text().strip().upper()
        print(f"\n📋 Control file: {control_state}")
        if control_state == "PAUSE":
            print("   (System will pause when it checks control file)")
        elif control_state == "RUN":
            print("   (System will continue running)")
    
    # Check instructions
    instructions_file = Path(__file__).parent / "instructions.md"
    if instructions_file.exists():
        instructions = instructions_file.read_text().strip()
        if instructions:
            print(f"\n📝 Current project goal:")
            print(f"   {instructions[:100]}...")
    
    print("\n💡 To stop the system:")
    print("   1. Set control.txt to 'PAUSE' (system will pause on next check)")
    print("   2. Or kill the process: kill <PID>")
    print("   3. Or find and kill: pkill -f 'python3.*main.py'")
    print("\n💡 Note: Use 'python3' command (not 'python') on macOS")

if __name__ == "__main__":
    check_status()

