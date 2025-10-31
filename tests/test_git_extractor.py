"""Tests for the git extractor module."""

import pytest
from pathlib import Path
from git import Repo
from brainet.core.extractors.git_extractor import GitExtractor

def test_git_extractor_initialization(test_repo):
    """Test GitExtractor initialization."""
    extractor = GitExtractor(test_repo)
    assert extractor.repo_path == test_repo
    assert isinstance(extractor.repo, Repo)

def test_branch_name(test_repo):
    """Test getting the current branch name."""
    extractor = GitExtractor(test_repo)
    assert extractor.branch_name == "main"

def test_repo_name(test_repo):
    """Test getting the repository name."""
    extractor = GitExtractor(test_repo)
    assert extractor.repo_name == "test_repo"

def test_modified_files(test_repo):
    """Test getting modified files."""
    # Create a new file
    new_file = test_repo / "new.py"
    new_file.write_text("print('hello')")
    
    # Modify an existing file
    (test_repo / "test.py").write_text("# Modified content")
    
    extractor = GitExtractor(test_repo)
    modified = extractor.get_modified_files()
    
    assert len(modified) == 2
    assert any(f.path == "new.py" and f.status == "added" for f in modified)
    assert any(f.path == "test.py" and f.status == "modified" for f in modified)

def test_recent_commits(test_repo):
    """Test getting recent commits."""
    repo = Repo(test_repo)
    
    # Add some commits
    (test_repo / "test.py").write_text("# Modified")
    repo.index.add(["test.py"])
    repo.index.commit("Update test.py")
    
    extractor = GitExtractor(test_repo)
    commits = extractor.get_recent_commits(limit=2)
    
    assert len(commits) == 2
    assert commits[0].message == "Update test.py"
    assert commits[1].message == "Initial commit"

def test_is_git_repo(test_repo, tmp_path):
    """Test git repository detection."""
    assert GitExtractor.is_git_repo(test_repo) is True
    assert GitExtractor.is_git_repo(tmp_path) is False