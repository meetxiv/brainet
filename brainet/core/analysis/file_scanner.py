"""
File Scanner Module - Source #2

Loads complete file content for all modified files, enabling the AI to understand
full context beyond just diffs.

This module:
- Loads full content of modified files
- Intelligently truncates massive files (>10k lines)
- Filters out binary/non-text files
- Provides smart truncation based on AST when needed
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import mimetypes


class FileScanner:
    """
    Scans and loads complete file content for modified files.
    
    This is Source #2 in the 5-source architecture - provides full code context.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize file scanner.
        
        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)
        self._text_extensions = self._get_text_extensions()
    
    def load_modified_files(self, file_paths: List[str]) -> Dict[str, str]:
        """
        Load full content of all modified files.
        
        Args:
            file_paths: List of relative file paths to load
            
        Returns:
            Dictionary mapping file_path -> file_content
        """
        file_contents = {}
        
        for file_path in file_paths:
            content = self.load_file(file_path)
            if content is not None:
                file_contents[file_path] = content
        
        return file_contents
    
    def load_file(self, file_path: str) -> Optional[str]:
        """
        Load a single file's content.
        
        Args:
            file_path: Relative path to file
            
        Returns:
            File content as string, or None if file can't be read
        """
        full_path = self.project_root / file_path
        
        # Check file exists
        if not full_path.exists():
            return None
        
        # Check if it's a file (not directory)
        if not full_path.is_file():
            return None
        
        # Check if text file
        if not self._is_text_file(full_path):
            return f"[Binary file: {file_path}]"
        
        try:
            # Read file
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Smart truncation for massive files
            lines = content.split('\n')
            if len(lines) > 10000:
                content = self._smart_truncate(content, file_path, lines)
            
            return content
            
        except PermissionError:
            return f"[Permission denied: {file_path}]"
        except Exception as e:
            return f"[Error reading {file_path}: {str(e)}]"
    
    def _is_text_file(self, file_path: Path) -> bool:
        """
        Check if file is a text file worth analyzing.
        
        Uses both extension checking and mimetype detection.
        """
        # Check extension first (fast)
        if file_path.suffix.lower() in self._text_extensions:
            return True
        
        # Try mimetype detection (slower but more accurate)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            return mime_type.startswith('text/') or mime_type in [
                'application/json',
                'application/xml',
                'application/javascript',
                'application/x-python',
                'application/x-sh'
            ]
        
        # Fallback: try reading first few bytes
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(512)
                # Check if chunk is mostly text (no null bytes)
                if b'\x00' in chunk:
                    return False
                # Try decoding as UTF-8
                try:
                    chunk.decode('utf-8')
                    return True
                except UnicodeDecodeError:
                    return False
        except:
            return False
    
    def _get_text_extensions(self) -> Set[str]:
        """Get set of text file extensions to analyze."""
        return {
            # Programming languages
            '.py', '.pyw', '.pyx', '.pyi',  # Python
            '.js', '.jsx', '.ts', '.tsx', '.mjs',  # JavaScript/TypeScript
            '.java', '.class', '.jar',  # Java
            '.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.hxx',  # C/C++
            '.cs', '.csx',  # C#
            '.go',  # Go
            '.rs',  # Rust
            '.rb', '.rake', '.gemspec',  # Ruby
            '.php', '.phtml',  # PHP
            '.swift',  # Swift
            '.kt', '.kts',  # Kotlin
            '.scala',  # Scala
            '.r', '.R',  # R
            '.m', '.mm',  # Objective-C
            '.lua',  # Lua
            '.pl', '.pm',  # Perl
            '.sh', '.bash', '.zsh', '.fish',  # Shell
            '.ps1',  # PowerShell
            '.bat', '.cmd',  # Batch
            
            # Web technologies
            '.html', '.htm', '.xhtml',  # HTML
            '.css', '.scss', '.sass', '.less',  # CSS
            '.vue', '.svelte',  # Frontend frameworks
            
            # Data formats
            '.json', '.jsonc', '.json5',  # JSON
            '.yaml', '.yml',  # YAML
            '.xml', '.xsd', '.xsl',  # XML
            '.toml',  # TOML
            '.ini', '.cfg', '.conf',  # Config
            '.csv', '.tsv',  # Tabular data
            
            # Documentation
            '.md', '.markdown', '.mdown', '.mkd',  # Markdown
            '.rst',  # reStructuredText
            '.txt', '.text',  # Plain text
            '.tex',  # LaTeX
            '.adoc', '.asciidoc',  # AsciiDoc
            
            # Database
            '.sql', '.mysql', '.pgsql',  # SQL
            
            # Other
            '.gitignore', '.dockerignore',
            '.env', '.env.example',
            'Dockerfile', 'Makefile', 'Rakefile',
            'requirements.txt', 'package.json', 'setup.py',
        }
    
    def _smart_truncate(self, content: str, file_path: str, lines: List[str]) -> str:
        """
        Intelligently truncate massive files.
        
        Strategy:
        - Keep first 5000 lines (includes imports, top-level definitions)
        - Keep last 1000 lines (includes recent code)
        - Add truncation marker in middle
        
        Future enhancement: Use AST to keep only functions/classes with changes.
        """
        truncated_lines = []
        
        # Keep first 5000 lines
        truncated_lines.extend(lines[:5000])
        
        # Add truncation notice
        removed_count = len(lines) - 6000
        truncated_lines.append("")
        truncated_lines.append(f"# ========== TRUNCATED: {removed_count} lines removed ==========")
        truncated_lines.append(f"# File too large ({len(lines)} lines total)")
        truncated_lines.append(f"# Showing first 5000 and last 1000 lines only")
        truncated_lines.append("# " + "=" * 60)
        truncated_lines.append("")
        
        # Keep last 1000 lines
        truncated_lines.extend(lines[-1000:])
        
        return '\n'.join(truncated_lines)
    
    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """
        Get metadata about a file.
        
        Returns:
            {
                "path": str,
                "size_bytes": int,
                "lines": int,
                "extension": str,
                "is_text": bool,
                "encoding": str
            }
        """
        full_path = self.project_root / file_path
        
        if not full_path.exists():
            return {"path": file_path, "error": "File not found"}
        
        info = {
            "path": file_path,
            "size_bytes": full_path.stat().st_size,
            "extension": full_path.suffix,
            "is_text": self._is_text_file(full_path)
        }
        
        # Get line count for text files
        if info["is_text"]:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    info["lines"] = len(f.readlines())
                    info["encoding"] = "utf-8"
            except:
                info["lines"] = 0
                info["encoding"] = "unknown"
        else:
            info["lines"] = 0
            info["encoding"] = "binary"
        
        return info
    
    def get_files_summary(self, file_paths: List[str]) -> Dict:
        """
        Get summary statistics for multiple files.
        
        Returns:
            {
                "total_files": int,
                "text_files": int,
                "binary_files": int,
                "total_lines": int,
                "largest_file": str,
                "file_types": dict  # extension -> count
            }
        """
        text_count = 0
        binary_count = 0
        total_lines = 0
        largest_file = None
        largest_size = 0
        file_types = {}
        
        for file_path in file_paths:
            info = self.get_file_info(file_path)
            
            if info.get("is_text"):
                text_count += 1
                total_lines += info.get("lines", 0)
            else:
                binary_count += 1
            
            # Track largest file
            size = info.get("size_bytes", 0)
            if size > largest_size:
                largest_size = size
                largest_file = file_path
            
            # Count file types
            ext = info.get("extension", "unknown")
            file_types[ext] = file_types.get(ext, 0) + 1
        
        return {
            "total_files": len(file_paths),
            "text_files": text_count,
            "binary_files": binary_count,
            "total_lines": total_lines,
            "largest_file": largest_file,
            "largest_size_bytes": largest_size,
            "file_types": file_types
        }
    
    def filter_text_files(self, file_paths: List[str]) -> List[str]:
        """
        Filter list to only text files worth analyzing.
        
        Returns:
            List of text file paths
        """
        text_files = []
        
        for file_path in file_paths:
            full_path = self.project_root / file_path
            if full_path.exists() and self._is_text_file(full_path):
                text_files.append(file_path)
        
        return text_files
