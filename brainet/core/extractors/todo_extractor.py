"""
TODO comment extraction module.

This module handles parsing and extracting TODO comments from source code files,
supporting multiple comment formats and providing surrounding context.
"""

import re
import os
from pathlib import Path
from typing import List, TextIO, Tuple, Optional

from ...utils.patterns import (
    TODO_PATTERN,
    is_code_file,
    should_ignore_file
)

import os
from pathlib import Path
from typing import List, TextIO, Tuple

from ...utils.patterns import (
    TODO_PATTERN,
    is_code_file,
    should_ignore_file
)
from ...storage.models.capsule import Todo

class TodoExtractor:
    """Extracts TODO comments from source code files."""

    def __init__(self, project_root: Path):
        """
        Initialize the TODO extractor.
        
        Args:
            project_root: Root directory to scan for TODOs
        """
        self.project_root = Path(project_root)
        # Common directories to ignore
        self.ignored_dirs = {
            'node_modules', 'venv', '.venv', '.git', '__pycache__',
            'dist', 'build', 'site-packages', '.pytest_cache',
            'bin', 'lib', '.vs', '.vscode', '.idea', '.mypy_cache',
            'downloads', 'cache', 'share', 'tmp'
        }
        self.todo_pattern = re.compile(
            r'^[^\S\n]*'             # Start of line + optional whitespace
            r'(?:#{1,2}|\/\/|\*)'    # Comment markers (# ## // *)
            r'\s*'                    # Optional whitespace
            r'(?:TODO|FIXME|NOTE)'   # Annotation types
            r'(?:\([^)]+\))?'        # Optional owner/date in parentheses
            r':\s*'                  # Colon followed by whitespace
            r'(.*?)$'                # The actual TODO text
        )

    def extract_todos(self) -> List[Todo]:
        """
        Extract all TODOs from code files in the root directory.
        
        Returns:
            List[Todo]: List of found TODOs with their context
        """
        todos = []
        code_files = self._find_code_files()  # Use the optimized file finder
        
        for file_path in code_files:
            # Files are already filtered by _find_code_files, no need to check again
                
            try:
                file_todos = self._extract_file_todos(file_path)
                todos.extend(file_todos)
            except UnicodeDecodeError:
                # Skip files that can't be decoded as text
                continue
            except Exception as e:
                # Log other errors but continue processing
                print(f"Error processing {file_path}: {e}")
                continue
        
        return todos

    def _is_text_file(self, path: Path) -> bool:
        """Check if file is a text file."""
        if path.name.startswith('.'):  # Skip hidden files
            return False
            
        # Common binary file extensions to skip
        binary_extensions = {
            '.pyc', '.pyo', '.pyd',  # Python bytecode
            '.exe', '.dll', '.so', '.dylib',  # Binaries
            '.zip', '.tar', '.gz', '.bz2', '.rar',  # Archives
            '.jpg', '.jpeg', '.png', '.gif', '.ico',  # Images
            '.pdf', '.doc', '.docx', '.ppt', '.pptx',  # Documents
            '.mp3', '.mp4', '.avi', '.mov',  # Media
            '.sqlite', '.db', '.dat',  # Data files
        }
        
        if path.suffix.lower() in binary_extensions:
            return False
            
        # Known text file extensions
        text_extensions = {
            '.py', '.pyi',  # Python
            '.js', '.jsx', '.ts', '.tsx',  # JavaScript/TypeScript
            '.html', '.htm', '.css', '.scss', '.less',  # Web
            '.txt', '.md', '.rst', '.csv',  # Text
            '.json', '.yaml', '.yml', '.toml', '.ini',  # Config
            '.sh', '.bash', '.zsh',  # Shell
            '.sql',  # SQL
            '.xml', '.svg',  # XML
            '.java', '.kt', '.scala',  # JVM
            '.c', '.cpp', '.h', '.hpp',  # C/C++
            '.rb', '.rake',  # Ruby
            '.php',  # PHP
            '.go',  # Go
            '.rs',  # Rust
        }
        
        return path.suffix.lower() in text_extensions

    def _find_code_files(self) -> List[Path]:
        """Find all code files in the root directory."""
        code_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            root_path = Path(root)
            
            # Don't check ignored_dirs against absolute path - only prune subdirectories
            # (The dirs[:] modification above handles that)
            
            for file in files:
                file_path = root_path / file
                
                # Skip if not a recognized code file
                if file_path.suffix.lower() not in {'.py', '.js', '.ts', '.jsx', '.tsx', '.java'}:
                    continue
                    
                try:
                    # Quick check if file is binary
                    with open(file_path, 'r', encoding='utf-8') as f:
                        f.readline()  # Just try reading one line
                except UnicodeDecodeError:
                    continue  # Skip binary files
                    
                code_files.append(file_path)
        
        return code_files
    
    def _extract_file_todos(self, file_path: Path) -> List[Todo]:
        """
        Extract TODOs from a single file.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List[Todo]: List of TODOs found in the file
        """
        todos = []
        
        # Get relative path for storing in the Todo object
        rel_path = file_path.relative_to(self.project_root)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.splitlines()
            
            # Process each line
            for i, line in enumerate(lines, 1):
                match = self.todo_pattern.search(line)
                if match:
                    todo_text = match.group(1).strip()
                    if todo_text:
                        context = self._get_detailed_context(lines, i, file_path)
                        function_info = self._extract_function_context(lines, i)
                        
                        # Build enhanced context including function/class info
                        enhanced_context = context
                        if function_info:
                            enhanced_context = f"{function_info}\n{context}"
                        
                        todos.append(Todo(
                            file=str(rel_path),
                            line=i,
                            text=todo_text,
                            context=enhanced_context
                        ))
                        
        except (UnicodeDecodeError, IOError) as e:
            print(f"Error reading {file_path}: {e}")
            
        return todos
    
    def _extract_function_context(self, lines: List[str], target_line: int) -> Optional[str]:
        """
        Extract function/class name where TODO is located.
        
        Args:
            lines: All lines in the file
            target_line: Line number (1-based)
            
        Returns:
            Function/class context or None
        """
        target_idx = target_line - 1
        
        # Search backwards for function/class definition
        function_pattern = re.compile(r'^\s*(?:async\s+)?def\s+(\w+)\s*\(')
        class_pattern = re.compile(r'^\s*class\s+(\w+)')
        
        current_function = None
        current_class = None
        
        for i in range(target_idx, -1, -1):
            line = lines[i]
            
            # Check for function
            func_match = function_pattern.search(line)
            if func_match and current_function is None:
                current_function = func_match.group(1)
            
            # Check for class
            class_match = class_pattern.search(line)
            if class_match and current_class is None:
                current_class = class_match.group(1)
            
            # Stop if we found both or hit beginning of file
            if current_function or i == 0:
                break
        
        # Build context string
        parts = []
        if current_class:
            parts.append(f"Class: {current_class}")
        if current_function:
            parts.append(f"Function: {current_function}")
        
        return " | ".join(parts) if parts else None
    
    def _get_detailed_context(self, lines: List[str], target_line: int, file_path: Path, context_lines: int = 5) -> str:
        """
        Get detailed surrounding context with line numbers.
        
        Args:
            lines: All lines in the file
            target_line: The line number (1-based)
            file_path: Path to the file
            context_lines: Number of lines before/after
            
        Returns:
            Formatted context string with line numbers
        """
        target_idx = target_line - 1
        start = max(0, target_idx - context_lines)
        end = min(len(lines), target_idx + context_lines + 1)
        
        context = []
        for i in range(start, end):
            line = lines[i].rstrip()
            marker = '>>>' if i == target_idx else '   '
            line_num = i + 1
            context.append(f"{marker} {line_num:4d} | {line}")
        
        return '\n'.join(context)
    
    def _create_todo(self, file_path: Path, line: int, text: str, context: str) -> Todo:
        """Create a Todo object with the given information."""
        return Todo(
            file=str(file_path),
            line=line,
            text=text.strip(),
            context=context
        )
    
    def _get_context(self, lines: List[str], target_line: int, context_lines: int = 2) -> str:
        """
        Get the surrounding context of a line.
        
        Args:
            lines: All lines in the file
            target_line: The line number to get context for (1-based)
            context_lines: Number of lines of context to include before and after
            
        Returns:
            str: The context string
        """
        # Convert 1-based line number to 0-based index
        target_idx = target_line - 1
        
        # Calculate valid line range
        start = max(0, target_idx - context_lines)
        end = min(len(lines), target_idx + context_lines + 1)
        
        # Extract context lines with line prefixes
        context = []
        for i in range(start, end):
            line = lines[i].rstrip()
            prefix = '>' if i == target_idx else ' '
            context.append(f"{prefix} {line}")
        
        return '\n'.join(context)