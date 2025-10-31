"""
Git state extraction module.

This module handles all Git-related operations for context extraction,
including retrieving modified files, commit history, and repository metadata.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import git
from git.repo import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError

from ...storage.models.capsule import ModifiedFile, Commit

class GitExtractor:
    """Extracts Git-related context from a repository."""
    
    def __init__(self, repo_path: Path):
        """
        Initialize the Git extractor.
        
        Args:
            repo_path: Path to the Git repository
            
        Raises:
            InvalidGitRepositoryError: If the path is not a valid Git repository
            NoSuchPathError: If the path doesn't exist
        """
        self.repo_path = repo_path
        self.repo = Repo(repo_path)
    
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
        except:
            pass  # No HEAD yet (empty repo)
        
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
    
    def get_file_diff(self, filepath: str, include_last_commit: bool = True) -> Optional[str]:
        """
        Get the diff for a specific modified file.
        
        Args:
            filepath: Relative path to the file
            include_last_commit: If True and no uncommitted changes, get diff from last commit
            
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
                
                # If no staged changes, try UNSTAGED changes (modified but not added)
                if not diff:
                    diff = self.repo.git.diff('HEAD', filepath)
                
                if not diff and include_last_commit:
                    # No uncommitted changes, try getting diff from LAST COMMIT
                    try:
                        diff = self.repo.git.diff('HEAD~1', 'HEAD', filepath)
                    except Exception:
                        pass  # No previous commit or error
            else:
                # No commits yet - just get the diff without HEAD reference
                diff = self.repo.git.diff(filepath)
                
                # If file is staged, get the full content as a new file
                if not diff and filepath in [item.a_path for item in self.repo.index.diff("HEAD", create_patch=True)] if has_commits else []:
                    full_path = self.repo_path / filepath
                    if full_path.exists():
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        return f"+++ NEW FILE (staged) +++\n{content[:2000]}"
            
            if not diff:
                # File might be untracked, try showing full content
                full_path = self.repo_path / filepath
                if full_path.exists() and filepath in self.repo.untracked_files:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return f"+++ NEW FILE (untracked) +++\n{content[:2000]}"  # Limit to 2000 chars
            
            return diff[:5000] if diff else None  # Limit diff size
        except Exception as e:
            return None
    
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