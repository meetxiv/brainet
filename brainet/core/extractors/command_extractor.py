"""
Terminal command history extractor.

This module extracts recent terminal commands from shell history files
to track what commands were run during a development session.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class CommandEntry:
    """Represents a terminal command entry."""
    command: str
    timestamp: Optional[datetime]
    shell: str  # 'zsh', 'bash', etc.
    exit_code: Optional[int] = None
    output: Optional[str] = None
    duration: Optional[float] = None


class CommandExtractor:
    """Extracts recent terminal commands from shell history."""
    
    def __init__(self, project_root: Path, lookback_minutes: int = 60):
        """
        Initialize the command extractor.
        
        Args:
            project_root: Root directory of the project
            lookback_minutes: How far back to look for commands (default: 60 minutes)
        """
        self.project_root = project_root
        self.lookback_minutes = lookback_minutes
        self.home = Path.home()
        self.tracked_commands: Dict[str, CommandEntry] = {}
        
    def _get_shell_history_file(self) -> Optional[Path]:
        """Detect and return the shell history file path."""
        # Check for common shell history files
        history_files = [
            self.home / '.zsh_history',
            self.home / '.bash_history',
            self.home / '.history',
        ]
        
        for hist_file in history_files:
            if hist_file.exists():
                return hist_file
        
        return None
    
    def _parse_zsh_history(self, lines: List[str], cutoff_time: datetime) -> List[CommandEntry]:
        """Parse zsh history format."""
        commands = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # zsh extended history format: : <timestamp>:<elapsed>;<command>
            if line.startswith(':'):
                try:
                    parts = line.split(';', 1)
                    if len(parts) == 2:
                        # Extract timestamp from ": 1234567890:0;"
                        timestamp_part = parts[0].strip(':').split(':')[0]
                        timestamp = datetime.fromtimestamp(int(timestamp_part))
                        command = parts[1].strip()
                        
                        if timestamp >= cutoff_time:
                            commands.append(CommandEntry(
                                command=command,
                                timestamp=timestamp,
                                shell='zsh'
                            ))
                except (ValueError, IndexError):
                    # If parsing fails, skip this entry
                    continue
            else:
                # Simple format without timestamp
                commands.append(CommandEntry(
                    command=line,
                    timestamp=None,
                    shell='zsh'
                ))
        
        return commands
    
    def _parse_bash_history(self, lines: List[str]) -> List[CommandEntry]:
        """Parse bash history format (no timestamps by default)."""
        commands = []
        
        for line in lines:
            line = line.strip()
            if line:
                commands.append(CommandEntry(
                    command=line,
                    timestamp=None,
                    shell='bash'
                ))
        
        return commands
    
    def extract_recent_commands(self, limit: int = 20) -> List[CommandEntry]:
        """
        Extract recent terminal commands.
        
        Args:
            limit: Maximum number of commands to return
            
        Returns:
            List of CommandEntry objects
        """
        history_file = self._get_shell_history_file()
        if not history_file:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=self.lookback_minutes)
        
        try:
            with open(history_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return []
        
        # Parse based on shell type
        if 'zsh' in history_file.name:
            commands = self._parse_zsh_history(lines, cutoff_time)
        else:
            # For bash and others, take the last N commands
            commands = self._parse_bash_history(lines[-limit:])
        
        # Filter out brainet commands to avoid recursion
        commands = [
            cmd for cmd in commands
            if not cmd.command.startswith('brainet')
        ]
        
        # Sort by timestamp if available
        commands_with_time = [c for c in commands if c.timestamp]
        commands_without_time = [c for c in commands if not c.timestamp]
        
        commands_with_time.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Combine and limit
        result = (commands_with_time + commands_without_time)[:limit]
        
        return result
    
    def get_project_related_commands(self, limit: int = 10) -> List[CommandEntry]:
        """
        Get commands that are likely related to the current project.
        
        Args:
            limit: Maximum number of commands to return
            
        Returns:
            List of CommandEntry objects
        """
        all_commands = self.extract_recent_commands(limit=50)
        
        # Filter for development-related commands
        dev_keywords = [
            'git', 'python', 'pip', 'npm', 'node', 'pytest', 'test',
            'make', 'cargo', 'go', 'java', 'mvn', 'gradle',
            'docker', 'kubectl', 'cd', 'ls', 'cat', 'vim', 'nano',
            'code', 'subl', 'atom'
        ]
        
        project_commands = []
        for cmd in all_commands:
            # Check if command contains any dev keywords
            cmd_lower = cmd.command.lower()
            if any(keyword in cmd_lower for keyword in dev_keywords):
                project_commands.append(cmd)
        
        return project_commands[:limit]
    
    def track_command_execution(self, command: str, exit_code: int, output: str = None, duration: float = None):
        """
        Track a command execution with its results.
        
        Args:
            command: Command that was executed
            exit_code: Exit code of the command
            output: Command output (optional)
            duration: Execution duration in seconds (optional)
        """
        entry = CommandEntry(
            command=command,
            timestamp=datetime.now(),
            shell=os.environ.get('SHELL', 'unknown').split('/')[-1],
            exit_code=exit_code,
            output=output[:500] if output else None,  # Limit output size
            duration=duration
        )
        self.tracked_commands[command] = entry
    
    def detect_command_pattern(self, commands: List[CommandEntry]) -> Dict[str, any]:
        """
        Detect patterns in command usage.
        
        Args:
            commands: List of command entries
            
        Returns:
            Dict with pattern analysis
        """
        patterns = {
            'testing': 0,
            'committing': 0,
            'debugging': 0,
            'running_code': 0,
            'failed_commands': 0,
            'successful_commands': 0
        }
        
        for cmd in commands:
            cmd_lower = cmd.command.lower()
            
            if 'test' in cmd_lower or 'pytest' in cmd_lower:
                patterns['testing'] += 1
            if 'git commit' in cmd_lower or 'git push' in cmd_lower:
                patterns['committing'] += 1
            if 'debug' in cmd_lower or 'pdb' in cmd_lower:
                patterns['debugging'] += 1
            if 'python' in cmd_lower or 'node' in cmd_lower or './':
                patterns['running_code'] += 1
            
            if cmd.exit_code is not None:
                if cmd.exit_code == 0:
                    patterns['successful_commands'] += 1
                else:
                    patterns['failed_commands'] += 1
        
        return patterns
    
    def get_test_commands(self) -> List[CommandEntry]:
        """Get all test-related commands."""
        all_commands = self.extract_recent_commands(limit=50)
        return [
            cmd for cmd in all_commands
            if 'test' in cmd.command.lower() or 'pytest' in cmd.command.lower()
        ]
    
    def get_failed_commands(self) -> List[CommandEntry]:
        """Get commands that failed (exit code != 0)."""
        return [
            cmd for cmd in self.tracked_commands.values()
            if cmd.exit_code is not None and cmd.exit_code != 0
        ]
