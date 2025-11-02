"""
Git state extraction module.

This module handles all Git-related operations for context extraction,
including retrieving modified files, commit history, and repository metadata.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import re

import git
from git.repo import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError

from ...storage.models.capsule import ModifiedFile, Commit

class GitExtractor:
    """Extracts Git-related context from a repository."""
    
    def __init__(self, repo_path: Path, ast_parser=None):
        """
        Initialize the Git extractor.
        
        Args:
            repo_path: Path to the Git repository
            ast_parser: Optional ASTParser instance for smart diff chunking
            
        Raises:
            InvalidGitRepositoryError: If the path is not a valid Git repository
            NoSuchPathError: If the path doesn't exist
        """
        self.repo_path = repo_path
        self.repo = Repo(repo_path)
        self.ast_parser = ast_parser  # For smart diff extraction
    
    @property
    def branch_name(self) -> Optional[str]:
        """Get the current branch name."""
        try:
            return self.repo.active_branch.name
        except TypeError:  # HEAD is detached
            return None
    
    @property
    def repo_name(self) -> str:
        """Get the repository name from the remote URL."""
        try:
            origin = self.repo.remote('origin')
            url = next(origin.urls)
            return url.split('/')[-1].replace('.git', '')
        except (ValueError, StopIteration):
            return self.repo_path.name
    
    def get_modified_files(self) -> List[ModifiedFile]:
        """
        Get a list of modified files in the working directory.
        
        Returns:
            List[ModifiedFile]: List of modified file objects
        """
        modified_files = []
        seen_paths = set()
        
        # Get staged changes (git diff --cached)
        try:
            # Check if repo has commits
            if self.repo.heads:
                # Normal case: compare against HEAD
                for item in self.repo.index.diff("HEAD"):
                    status = self._get_change_type(item)
                    path = item.a_path if item.a_path else item.b_path
                    if path not in seen_paths:
                        modified_files.append(ModifiedFile(
                            path=path,
                            status=status,
                            last_modified=self._get_file_last_modified(path)
                        ))
                        seen_paths.add(path)
            else:
                # Fresh repo: get staged files from index
                for path in self.repo.index.entries.keys():
                    file_path = path[0]  # Entry key is (path, stage)
                    if file_path not in seen_paths and not self._should_ignore_file(file_path):
                        modified_files.append(ModifiedFile(
                            path=file_path,
                            status='added',
                            last_modified=self._get_file_last_modified(file_path)
                        ))
                        seen_paths.add(file_path)
        except Exception as e:
            pass  # Fallback to other methods
        
        # Get unstaged changes (git diff)
        for item in self.repo.index.diff(None):
            status = self._get_change_type(item)
            path = item.a_path if item.a_path else item.b_path
            if path not in seen_paths:
                modified_files.append(ModifiedFile(
                    path=path,
                    status=status,
                    last_modified=self._get_file_last_modified(path)
                ))
                seen_paths.add(path)
        
        # Include untracked files - users want to see new files they're working on
        for untracked_path in self.repo.untracked_files:
            # Skip noise files (.pyc, __pycache__, etc.)
            if not self._should_ignore_file(untracked_path):
                if untracked_path not in seen_paths:
                    modified_files.append(ModifiedFile(
                        path=untracked_path,
                        status='untracked',
                        last_modified=self._get_file_last_modified(untracked_path)
                    ))
                    seen_paths.add(untracked_path)
        
        return modified_files
    
    def _should_ignore_file(self, filepath: str) -> bool:
        """Check if file should be ignored (build artifacts, caches, etc.)."""
        ignore_patterns = [
            '__pycache__', '.pyc', '.pyo', '.pyd',
            'node_modules/', '.git/', '.brainet/',
            '.egg-info/', 'dist/', 'build/',
            '.DS_Store', '.pytest_cache/', '.venv/', 'venv/'
        ]
        return any(pattern in filepath for pattern in ignore_patterns)
    
    def get_recent_commits(self, limit: int = 10) -> List[Dict]:
            """Get recent commits from the repository."""
            commits = []
            try:
                # Check if repository has any commits
                if not self.repo.heads:  # No branches = no commits yet
                    return []
                
                for commit in self.repo.iter_commits(max_count=limit):
                    commits.append({
                        'hash': commit.hexsha[:7],
                        'message': commit.message.strip(),
                        'author': commit.author.name,
                        'timestamp': datetime.fromtimestamp(commit.committed_date).isoformat(),
                        'files_changed': len(commit.stats.files)
                    })
            except ValueError as e:
                # Handle "Reference does not exist" error for repos with no commits
                return []
            except Exception as e:
                print(f"Warning: Could not get commits: {e}")
                return []
            
            return commits
    
    def get_file_diff(self, filepath: str, staged_only: bool = False) -> Optional[str]:
        """
        Get the diff for a specific modified file with smart chunking.
        
        Uses AST parser (if available) to intelligently extract only changed
        functions/classes instead of blind truncation.
        
        Args:
            filepath: Relative path to the file
            staged_only: If True, only return diff for staged files (git diff --cached)
            
        Returns:
            Diff string or None if file not modified
        """
        try:
            diff = None
            
            # Check if repo has commits (HEAD exists)
            has_commits = bool(self.repo.heads)
            
            if has_commits:
                # Try STAGED changes first (files that were git added)
                diff = self.repo.git.diff('--cached', 'HEAD', filepath)
                
                # If no staged changes and not staged_only, try UNSTAGED changes
                if not diff and not staged_only:
                    diff = self.repo.git.diff('HEAD', filepath)
            else:
                # No commits yet - get diff for new repo
                # Must use --cached to see staged files in new repo
                diff = self.repo.git.diff('--cached', filepath)
                
                # If not staged and not staged_only, show unstaged
                if not diff and not staged_only:
                    diff = self.repo.git.diff(filepath)
            
            if not diff and not staged_only:
                # File might be untracked, show full content in proper diff format
                full_path = self.repo_path / filepath
                if full_path.exists() and filepath in self.repo.untracked_files:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    # Format as proper diff with + prefix for each line
                    diff_lines = [f"+{line}" for line in content.split('\n')[:100]]  # Limit lines
                    return f"+++ NEW FILE (untracked) +++\n" + '\n'.join(diff_lines)
            
            # Smart diff extraction using AST (if available and it's a Python file)
            if diff and self.ast_parser and filepath.endswith('.py'):
                smart_diff = self._extract_smart_diff(diff, filepath)
                if smart_diff:
                    return smart_diff
            
            # Fallback to simple truncation
            return diff[:5000] if diff else None
        except Exception as e:
            return None
    
    def _extract_smart_diff(self, diff: str, filepath: str) -> Optional[str]:
        """
        Extract diff intelligently using AST to show only changed functions/classes.
        
        This replaces blind 5000-char truncation with semantic extraction.
        
        Args:
            diff: Raw git diff output
            filepath: Path to the file
            
        Returns:
            Smartly extracted diff showing full changed functions
        """
        try:
            # Parse diff to find changed line numbers
            changed_lines = self._parse_changed_lines_from_diff(diff)
            if not changed_lines:
                return diff[:5000]  # Fallback if parsing fails
            
            # Load file content and parse with AST
            full_path = self.repo_path / filepath
            if not full_path.exists():
                return diff[:5000]
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
            
            # Parse file with AST to get structure
            structure = self.ast_parser.parse_file(filepath, file_content)
            if structure.get('error'):
                return diff[:5000]  # Fallback if AST parsing fails
            
            # Find which functions/classes contain the changes
            changed_entities = self.ast_parser.find_changed_entities(filepath, changed_lines)
            
            if not changed_entities:
                return diff[:5000]  # No entities found, use fallback
            
            # Extract full code for changed entities
            lines = file_content.split('\n')
            extracted_parts = []
            
            extracted_parts.append(f"# Smart diff for {filepath}")
            extracted_parts.append(f"# Changed lines: {changed_lines[:10]}")  # Show first 10
            extracted_parts.append(f"# Affected {len(changed_entities)} code entity(ies)\n")
            
            for entity in changed_entities:
                entity_type = entity['type']
                entity_name = entity['name']
                line_start = entity['line_start']
                line_end = entity['line_end']
                
                # Add header
                if entity_type == 'class':
                    methods = entity.get('changed_methods', [])
                    if methods:
                        extracted_parts.append(f"\n### CLASS: {entity_name} (changed methods: {', '.join(methods)})")
                    else:
                        extracted_parts.append(f"\n### CLASS: {entity_name}")
                else:
                    extracted_parts.append(f"\n### FUNCTION: {entity_name}")
                
                extracted_parts.append(f"# Lines {line_start}-{line_end}\n")
                
                # Extract entity code with context (3 lines before/after)
                context_start = max(0, line_start - 4)  # -1 for 0-indexing, -3 for context
                context_end = min(len(lines), line_end + 3)
                
                entity_lines = lines[context_start:context_end]
                
                # Add line numbers and highlight changed lines
                for i, line in enumerate(entity_lines, start=context_start + 1):
                    if i in changed_lines:
                        extracted_parts.append(f">>> {i:4d} | {line}")  # Highlight changed
                    else:
                        extracted_parts.append(f"    {i:4d} | {line}")
                
                extracted_parts.append("")  # Empty line between entities
            
            result = '\n'.join(extracted_parts)
            
            # If still too long, truncate but at least we tried
            if len(result) > 8000:
                result = result[:8000] + "\n\n... [Smart diff truncated - too large]"
            
            return result
            
        except Exception as e:
            # If anything fails, fallback to simple truncation
            return diff[:5000]
    
    def _parse_changed_lines_from_diff(self, diff: str) -> List[int]:
        """
        Parse git diff to extract line numbers that were changed.
        
        Args:
            diff: Raw git diff output
            
        Returns:
            List of line numbers that have changes (additions/modifications)
        """
        changed_lines = []
        current_line = 0
        
        for line in diff.split('\n'):
            # Look for hunk headers like: @@ -10,7 +10,8 @@
            if line.startswith('@@'):
                # Extract new file line number
                match = re.search(r'\+(\d+)', line)
                if match:
                    current_line = int(match.group(1))
                continue
            
            # Track additions and modifications (not deletions)
            if line.startswith('+') and not line.startswith('+++'):
                changed_lines.append(current_line)
                current_line += 1
            elif not line.startswith('-'):
                # Context line (exists in both versions)
                current_line += 1
        
        return changed_lines
    
    def get_staged_changes(self) -> List[Dict[str, str]]:
        """
        Get files that are staged for commit.
        
        Returns:
            List of dicts with 'path' and 'status'
        """
        staged = []
        try:
            diff_index = self.repo.index.diff('HEAD')
            for diff in diff_index:
                staged.append({
                    'path': diff.a_path or diff.b_path,
                    'status': self._get_change_type(diff)
                })
        except Exception:
            pass
        return staged
    
    def get_staged_files_with_diffs(self) -> List[Dict[str, str]]:
        """
        Get ONLY staged files with their diffs - for current session analysis.
        Uses smart diff extraction with AST for Python files.
        
        Returns:
            List of dicts with 'path', 'status', and 'diff'
        """
        staged_files = []
        try:
            # Get staged files
            diff_index = self.repo.index.diff('HEAD')
            for diff in diff_index:
                file_path = diff.a_path or diff.b_path
                
                # Get diff using smart extraction
                diff_content = self.get_file_diff(file_path, staged_only=True)
                
                staged_files.append({
                    'path': file_path,
                    'status': self._get_change_type(diff),
                    'diff': diff_content if diff_content else ''
                })
        except Exception as e:
            # No HEAD yet (empty repo) - try getting all staged files
            try:
                for item in self.repo.index.entries:
                    file_path = item[0]
                    full_path = self.repo_path / file_path
                    if full_path.exists():
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        # Format with proper + prefixes
                        diff_lines = [f"+{line}" for line in content.split('\n')[:100]]
                        staged_files.append({
                            'path': file_path,
                            'status': 'added',
                            'diff': f"+++ NEW FILE +++\n" + '\n'.join(diff_lines)
                        })
            except Exception:
                pass
        
        return staged_files
    
    def get_uncommitted_changes(self) -> List[Dict[str, str]]:
        """
        Get files with uncommitted changes (unstaged).
        
        Returns:
            List of dicts with 'path' and 'status'
        """
        uncommitted = []
        try:
            diff_index = self.repo.index.diff(None)  # Unstaged changes
            for diff in diff_index:
                uncommitted.append({
                    'path': diff.a_path or diff.b_path,
                    'status': self._get_change_type(diff)
                })
            
            # Add untracked files
            for path in self.repo.untracked_files:
                uncommitted.append({
                    'path': path,
                    'status': 'added'
                })
        except Exception:
            pass
        return uncommitted
    
    def get_last_commit_changes(self) -> List[Dict[str, str]]:
        """
        Get files changed in the last commit (fallback when no uncommitted changes).
        
        Returns:
            List of dicts with 'path', 'status', and 'additions'/'deletions'
        """
        changes = []
        try:
            # Get the last commit
            last_commit = next(self.repo.iter_commits(max_count=1))
            
            # If it's the first commit, compare with empty tree
            if not last_commit.parents:
                # First commit - compare with empty tree
                diff_index = last_commit.diff(None, create_patch=True)
            else:
                # Regular commit - compare with parent
                diff_index = last_commit.parents[0].diff(last_commit, create_patch=True)
            
            for diff in diff_index:
                path = diff.b_path if diff.b_path else diff.a_path
                
                # Count additions and deletions
                additions = 0
                deletions = 0
                if diff.diff:
                    diff_text = diff.diff.decode('utf-8', errors='ignore')
                    for line in diff_text.split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            additions += 1
                        elif line.startswith('-') and not line.startswith('---'):
                            deletions += 1
                
                changes.append({
                    'path': path,
                    'status': self._get_change_type(diff),
                    'additions': additions,
                    'deletions': deletions
                })
        except Exception as e:
            pass  # No commits yet or error
        
        return changes
    
    def get_file_content_snippet(self, filepath: str, line_number: Optional[int] = None, context_lines: int = 5) -> Optional[str]:
        """
        Get a snippet of file content around a specific line.
        
        Args:
            filepath: Relative path to the file
            line_number: Center line number (if None, returns first N lines)
            context_lines: Number of lines of context around the target line
            
        Returns:
            Code snippet or None if file not found
        """
        try:
            full_path = self.repo_path / filepath
            if not full_path.exists():
                return None
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if line_number is None:
                # Return first N lines
                snippet_lines = lines[:context_lines * 2]
            else:
                # Return lines around target line (1-indexed)
                start = max(0, line_number - context_lines - 1)
                end = min(len(lines), line_number + context_lines)
                snippet_lines = lines[start:end]
            
            # Add line numbers
            if line_number is None:
                start_line = 1
            else:
                start_line = max(1, line_number - context_lines)
            
            numbered_lines = []
            for i, line in enumerate(snippet_lines, start=start_line):
                marker = '>>> ' if i == line_number else '    '
                numbered_lines.append(f"{marker}{i:4d} | {line.rstrip()}")
            
            return '\n'.join(numbered_lines)
        except Exception:
            return None
    
    def get_last_commit_message(self) -> Optional[str]:
        """Get the last commit message."""
        try:
            return self.repo.head.commit.message.strip()
        except Exception:
            return None
    
    def get_branch_tracking_info(self) -> Dict[str, any]:
        """
        Get information about branch tracking status.
        
        Returns:
            Dict with commits ahead/behind remote
        """
        try:
            branch = self.repo.active_branch
            tracking = branch.tracking_branch()
            if tracking:
                ahead = sum(1 for _ in self.repo.iter_commits(f'{tracking.name}..{branch.name}'))
                behind = sum(1 for _ in self.repo.iter_commits(f'{branch.name}..{tracking.name}'))
                return {
                    'ahead': ahead,
                    'behind': behind,
                    'remote_branch': tracking.name
                }
        except Exception:
            pass
        return {'ahead': 0, 'behind': 0, 'remote_branch': None}
    
    def _get_change_type(self, diff) -> str:
        """Convert a git diff change type to a status string."""
        if diff.deleted_file:
            return 'deleted'
        elif diff.new_file:
            return 'added'
        else:
            return 'modified'
    
    def _get_file_last_modified(self, filepath: str) -> datetime:
        """Get the last modification time of a file."""
        try:
            path = self.repo_path / filepath
            return datetime.fromtimestamp(path.stat().st_mtime)
        except (FileNotFoundError, OSError):
            return datetime.utcnow()
    
    @staticmethod
    def is_git_repo(path: Path) -> bool:
        """
        Check if a path is a Git repository.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if path is a Git repository, False otherwise
        """
        try:
            _ = Repo(path)
            return True
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False