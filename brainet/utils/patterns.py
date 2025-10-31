"""
Regular expression patterns for extracting development context.

This module contains compiled regex patterns used throughout Brainet,
particularly for extracting TODOs and other code annotations.
"""

import re
from typing import Pattern

# Matches TODO comments in code or docstrings
TODO_PATTERN: Pattern = re.compile(
    r'^[^\S\n]*'              # Start of line + optional whitespace
    r'(?:#{1,2}|\/\/|\*|\s+)' # Comment markers (# ## // *) or docstring space
    r'(?:TODO|FIXME|NOTE)'    # Annotation types
    r'(?:\([^)]+\))?'         # Optional owner/date in parentheses
    r':\s*'                   # Colon followed by whitespace
    r'(.*?)$',                # The actual TODO text
    re.IGNORECASE | re.MULTILINE
)

# File patterns to ignore during TODO scanning
IGNORE_PATTERNS = [
    '.git', '.pytest_cache', '__pycache__', 
    '.venv', 'venv', '.env', 'node_modules',
    'dist', 'build', 'site-packages', '.vs',
    '.vscode', '.idea', '.mypy_cache',
    'downloads', 'cache', 'share', 'tmp'
]

# File patterns to ignore by extension
IGNORE_EXTENSIONS = [
    '*.pyc', '*.pyo', '*.pyd',  # Python bytecode
    '*.class', '*.jar',  # Java
    '*.o', '*.so', '*.dll', '*.dylib',  # Binaries
    '*.gz', '*.tar', '*.zip', '*.rar',  # Archives
    '*.jpg', '*.png', '*.gif', '*.ico',  # Images
    '.DS_Store'  # macOS
]

# Common code file extensions to scan
CODE_FILE_PATTERNS = [
    '*.py',    # Python
    '*.js',    # JavaScript
    '*.ts',    # TypeScript
    '*.jsx',   # React JSX
    '*.tsx',   # React TSX
    '*.cpp',   # C++
    '*.hpp',   # C++ headers
    '*.c',     # C
    '*.h',     # C headers
    '*.java',  # Java
    '*.go',    # Go
    '*.rb',    # Ruby
    '*.rs',    # Rust
    '*.php',   # PHP
]

def is_code_file(filename: str) -> bool:
    """
    Check if a file is a recognized code file based on its extension.
    
    Args:
        filename: The name of the file to check
        
    Returns:
        bool: True if the file is a recognized code file, False otherwise
    """
    from fnmatch import fnmatch
    return any(fnmatch(filename.lower(), pattern) for pattern in CODE_FILE_PATTERNS)

def should_ignore_file(filepath: str) -> bool:
    """
    Check if a file should be ignored based on ignore patterns.
    
    Args:
        filepath: The path to the file to check
        
    Returns:
        bool: True if the file should be ignored, False otherwise
    """
    from fnmatch import fnmatch
    from pathlib import Path
    
    path = Path(filepath)
    
    # Check if any part of the path matches ignored directories
    path_parts = path.parts
    if any(ignored in path_parts for ignored in IGNORE_PATTERNS):
        return True
        
    # Check file extension patterns
    if any(fnmatch(path.name, pattern) for pattern in IGNORE_EXTENSIONS):
        return True
        
    return False