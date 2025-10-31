"""
Core extractors package for Brainet.

This package contains modules for extracting various types of development context:
- git_extractor: Extracts Git repository state and history
- todo_extractor: Extracts TODO comments from code files
- file_extractor: Monitors and extracts file system changes
"""

# These imports are used by other modules
from .git_extractor import GitExtractor
from .todo_extractor import TodoExtractor
from .file_extractor import FileExtractor

__all__ = ['GitExtractor', 'TodoExtractor', 'FileExtractor']