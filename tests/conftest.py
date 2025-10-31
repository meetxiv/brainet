"""Test configuration and fixtures."""

import os
import pytest
from pathlib import Path
from git import Repo
from brainet.core.context_capture import ContextCapture
from brainet.storage.models.capsule import Capsule

@pytest.fixture
def test_repo(tmp_path):
    """Create a temporary Git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)
    
    # Create test files with TODOs
    test_py = repo_path / "test.py"
    test_py.write_text("# TODO: implement this\ndef test():\n    pass\n")
    repo.index.add(["test.py"])
    
    main_py = repo_path / "main.py"
    main_py.write_text("def main():\n    # FIXME: add error handling\n    pass\n")
    repo.index.add(["main.py"])
    
    # Create a test directory structure
    src_dir = repo_path / "src"
    src_dir.mkdir()
    
    # Add files with TODOs in subdirectories
    sub_file = src_dir / "helper.py"
    sub_file.write_text("# TODO: add helper functions\ndef helper():\n    pass\n")
    repo.index.add(["src/helper.py"])    # Initial commit
    repo.index.add(["test.py", "main.py"])
    repo.index.commit("Initial commit")
    
    return repo_path

@pytest.fixture
def context_capture(test_repo):
    """Create a ContextCapture instance with a test repository."""
    return ContextCapture(test_repo)

@pytest.fixture
def sample_capsule(test_repo):
    """Create a sample context capsule for testing."""
    return Capsule(
        project={
            "name": "test_repo",
            "root_path": test_repo,
            "git_branch": "master",
            "git_repo": "test_repo"
        },
        context={
            "modified_files": [],
            "recent_commits": [],
            "todos": [],
            "active_file": None
        }
    )