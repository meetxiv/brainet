"""
File monitoring and extraction module.

This module handles tracking file system changes and maintaining state about
which files are being actively worked on. It provides detailed tracking of
file changes, activity patterns, and contextual analysis of development focus.
"""

import time
import re
import ast
import difflib
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, DefaultDict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

class ChangeType(Enum):
    """Types of file system changes."""
    CREATED = 'created'
    MODIFIED = 'modified'
    DELETED = 'deleted'
    MOVED = 'moved'

@dataclass
class FileChange:
    """Represents a single file change event."""
    path: Path
    change_type: ChangeType
    timestamp: float
    diff: Optional[str] = None
    old_path: Optional[Path] = None  # For moved files

@dataclass
class ActivityScore:
    """Track file activity scoring."""
    last_access: float = 0.0
    access_count: int = 0
    edit_count: int = 0
    time_spent: float = 0.0
    
    def update_access(self, timestamp: float):
        """Update access metrics."""
        if self.last_access > 0:
            self.time_spent += timestamp - self.last_access
        self.last_access = timestamp
        self.access_count += 1
    
    def update_edit(self, timestamp: float):
        """Update edit metrics."""
        self.update_access(timestamp)
        self.edit_count += 1

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system change events with enhanced tracking."""
    
    def __init__(self):
        """Initialize the change handler with enhanced metrics."""
        self.changes: List[FileChange] = []
        self.file_contents: Dict[Path, str] = {}
        self.activity_scores: DefaultDict[Path, ActivityScore] = defaultdict(ActivityScore)
        self.active_file: Optional[Path] = None
        self._active_threshold = 300  # 5 minutes
    
    def _update_contents(self, path: Path) -> Optional[str]:
        """Update tracked file contents and return diff if modified."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                new_content = f.read()
                old_content = self.file_contents.get(path)
                if old_content:
                    diff = '\n'.join(difflib.unified_diff(
                        old_content.splitlines(),
                        new_content.splitlines(),
                        n=3
                    ))
                    self.file_contents[path] = new_content
                    return diff if diff else None
                else:
                    self.file_contents[path] = new_content
                    return None
        except Exception:
            return None
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events with diff tracking."""
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        timestamp = time.time()
        
        # Update activity score
        self.activity_scores[path].update_edit(timestamp)
        
        # Get diff if possible
        diff = self._update_contents(path)
        
        # Record change
        change = FileChange(
            path=path,
            change_type=ChangeType.MODIFIED,
            timestamp=timestamp,
            diff=diff
        )
        self.changes.append(change)
        
        # Update active file if this is the most recent edit
        self._update_active_file(path, timestamp)
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        timestamp = time.time()
        
        # Update activity score
        self.activity_scores[path].update_edit(timestamp)
        
        # Record creation
        change = FileChange(
            path=path,
            change_type=ChangeType.CREATED,
            timestamp=timestamp
        )
        self.changes.append(change)
        
        # Cache initial contents
        self._update_contents(path)
        
        # Update active file
        self._update_active_file(path, timestamp)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        timestamp = time.time()
        
        # Record deletion
        change = FileChange(
            path=path,
            change_type=ChangeType.DELETED,
            timestamp=timestamp
        )
        self.changes.append(change)
        
        # Clean up tracking
        if path in self.file_contents:
            del self.file_contents[path]
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename events."""
        if event.is_directory:
            return
            
        old_path = Path(event.src_path)
        new_path = Path(event.dest_path)
        timestamp = time.time()
        
        # Update activity score for new path
        self.activity_scores[new_path].update_edit(timestamp)
        
        # Record move
        change = FileChange(
            path=new_path,
            change_type=ChangeType.MOVED,
            timestamp=timestamp,
            old_path=old_path
        )
        self.changes.append(change)
        
        # Update content tracking
        if old_path in self.file_contents:
            self.file_contents[new_path] = self.file_contents.pop(old_path)
        
        # Update active file reference if needed
        if self.active_file == old_path:
            self.active_file = new_path
    
    def _update_active_file(self, path: Path, timestamp: float):
        """Update active file based on recent activity."""
        self.active_file = path
        
        # Clean up old activity scores
        expired = time.time() - self._active_threshold
        for file_path in list(self.activity_scores.keys()):
            score = self.activity_scores[file_path]
            if score.last_access < expired:
                del self.activity_scores[file_path]

class FileExtractor:
    """Tracks file system changes in real-time with enhanced metrics."""
    
    def __init__(self, root_path: Path, ignore_patterns: List[str] = None):
        """
        Initialize the file extractor.
        
        Args:
            root_path: Root directory to monitor
            ignore_patterns: List of glob patterns to ignore
        """
        self.root_path = root_path
        self.handler = FileChangeHandler()
        self.observer = Observer()
        
        # Default ignore patterns
        self.ignore_patterns = ignore_patterns or [
            '**/.git/**',
            '**/__pycache__/**',
            '**/node_modules/**',
            '**/.pytest_cache/**',
            '**/*.pyc'
        ]
        
        self.observer.schedule(self.handler, str(root_path), recursive=True)
        self._started = False
    
    def start(self):
        """Start monitoring file changes."""
        if not self._started:
            self.observer.start()
            self._started = True
    
    def stop(self):
        """Stop monitoring file changes."""
        if self._started:
            self.observer.stop()
            self.observer.join()
            self._started = False
    
    @property
    def modified_files(self) -> List[Path]:
        """Get list of modified files."""
        return [
            change.path for change in self.handler.changes
            if change.change_type == ChangeType.MODIFIED
        ]
    
    @property
    def active_file(self) -> Optional[Path]:
        """Get the currently active file."""
        return self.handler.active_file
    
    def get_changes(self, since: Optional[float] = None) -> List[FileChange]:
        """
        Get list of file changes since given timestamp.
        
        Args:
            since: Optional timestamp to filter changes from
            
        Returns:
            List of FileChange objects
        """
        if since is None:
            return self.handler.changes
        return [
            change for change in self.handler.changes
            if change.timestamp >= since
        ]
    
    def get_file_info(self, path: Path) -> Dict[str, any]:
        """
        Get detailed information about a file.
        
        Args:
            path: Path to the file
            
        Returns:
            Dict containing file information
        """
        try:
            stat = path.stat()
            relative_path = path.relative_to(self.root_path)
            score = self.handler.activity_scores.get(path, ActivityScore())
            
            return {
                'path': str(relative_path),
                'extension': path.suffix,
                'size': stat.st_size,
                'last_modified': stat.st_mtime,
                'created': stat.st_ctime,
                'activity': {
                    'last_access': score.last_access,
                    'access_count': score.access_count,
                    'edit_count': score.edit_count,
                    'time_spent': score.time_spent
                }
            }
        except (FileNotFoundError, OSError):
            return {
                'path': str(path.relative_to(self.root_path)),
                'error': 'File not accessible'
            }
    
    def get_active_files(self, limit: int = 5) -> List[Dict[str, any]]:
        """
        Get list of most actively edited files.
        
        Args:
            limit: Maximum number of files to return
            
        Returns:
            List of file info dicts sorted by activity
        """
        sorted_files = sorted(
            self.handler.activity_scores.items(),
            key=lambda x: (x[1].edit_count, x[1].time_spent),
            reverse=True
        )[:limit]
        
        return [self.get_file_info(path) for path, _ in sorted_files]
    
    def get_file_diff(self, path: Path) -> Optional[str]:
        """
        Get the latest diff for a file if available.
        
        Args:
            path: Path to the file
            
        Returns:
            Latest diff as string or None
        """
        changes = [c for c in reversed(self.handler.changes)
                  if c.path == path and c.diff is not None]
        return changes[0].diff if changes else None
    
    def clear_history(self):
        """Clear the change history and reset metrics."""
        self.handler.changes.clear()
        self.handler.file_contents.clear()
    
    def extract_modified_functions(self, file_path: Path) -> List[Dict[str, any]]:
        """
        Extract which functions/classes were modified in a Python file.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of dicts with function/class modification info
        """
        if file_path.suffix != '.py':
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            modified_items = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    modified_items.append({
                        'type': 'function',
                        'name': node.name,
                        'line_start': node.lineno,
                        'line_end': node.end_lineno,
                        'is_async': isinstance(node, ast.AsyncFunctionDef),
                        'args': [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    modified_items.append({
                        'type': 'class',
                        'name': node.name,
                        'line_start': node.lineno,
                        'line_end': node.end_lineno,
                        'methods': methods
                    })
            
            return modified_items
        except (SyntaxError, FileNotFoundError):
            return []
    
    def detect_change_pattern(self, file_path: Path) -> str:
        """
        Detect if changes are new code, refactoring, or debugging.
        
        Args:
            file_path: Path to the file
            
        Returns:
            'new_code', 'refactoring', 'debugging', or 'unknown'
        """
        diff = self.get_file_diff(file_path)
        if not diff:
            return 'unknown'
        
        added_lines = [l for l in diff.split('\n') if l.startswith('+') and not l.startswith('+++')]
        removed_lines = [l for l in diff.split('\n') if l.startswith('-') and not l.startswith('---')]
        
        # Check for debugging patterns
        debug_patterns = [r'print\(', r'console\.log', r'debug', r'breakpoint']
        has_debug = any(re.search(pattern, line, re.IGNORECASE) for pattern in debug_patterns for line in added_lines)
        
        if has_debug:
            return 'debugging'
        
        # More additions than deletions suggests new code
        if len(added_lines) > len(removed_lines) * 2:
            return 'new_code'
        
        # Similar additions/deletions suggests refactoring
        if abs(len(added_lines) - len(removed_lines)) < 5:
            return 'refactoring'
        
        return 'unknown'
    
    def get_file_snapshot(self, file_path: Path) -> Optional[str]:
        """
        Get current snapshot of file content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content or None
        """
        return self.handler.file_contents.get(file_path)
        self.handler.activity_scores.clear()
        self.handler.active_file = None