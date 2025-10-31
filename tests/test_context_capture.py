"""Tests for the context capture orchestrator."""

import pytest
from pathlib import Path
from brainet.core.context_capture import ContextCapture
from brainet.storage.models.capsule import Capsule, ProjectInfo

def test_context_capture_initialization(test_repo):
    """Test ContextCapture initialization."""
    capture = ContextCapture(test_repo)
    
    assert capture.project_root == test_repo
    assert capture.storage_dir == test_repo / '.brainet' / 'capsules'
    assert capture.git_extractor is not None
    assert capture.todo_extractor is not None
    assert capture.file_extractor is not None

def test_start_stop_monitoring(test_repo):
    """Test starting and stopping file monitoring."""
    capture = ContextCapture(test_repo)
    
    capture.start_monitoring()
    assert capture.file_extractor._started
    
    capture.stop_monitoring()
    assert not capture.file_extractor._started

def test_capture_context(test_repo):
    """Test capturing the current context."""
    capture = ContextCapture(test_repo)
    capsule = capture.capture_context()
    
    assert capsule.project.name == test_repo.name
    assert capsule.project.root_path == test_repo
    assert capsule.project.git_branch in ("main", "master")  # Git's default branch can be either
    assert len(capsule.context.todos) == 3  # From our test files (test.py, main.py, src/helper.py)
    assert capsule.context.active_file is None  # No active file yet

def test_context_retrieval(test_repo):
    """Test retrieving saved context."""
    capture = ContextCapture(test_repo)
    
    # Initially no context
    assert capture.get_latest_context() is None
    
    # Save a context
    capsule = capture.capture_context()
    capture.capsule_manager.save_capsule(capsule)
    
    # Retrieve it
    latest = capture.get_latest_context()
    assert latest is not None
    assert latest.metadata.timestamp == capsule.metadata.timestamp

def test_capsule_listing(test_repo):
    """Test listing available capsules."""
    capture = ContextCapture(test_repo)
    
    # Create multiple capsules with unique timestamps
    from datetime import datetime, timedelta
    base_time = datetime.utcnow()
    for i in range(3):
        # Create capsule but don't save it yet
        capsule = Capsule(
            project=ProjectInfo(
                name=capture.project_root.name,
                root_path=capture.project_root,
                git_branch=capture.git_extractor.branch_name if capture.git_extractor else None,
                git_repo=capture.git_extractor.repo_name if capture.git_extractor else None
            ),
            context=capture.build_context()
        )
        # Set timestamp and save once
        capsule.metadata.timestamp = base_time + timedelta(minutes=i)
        capture.capsule_manager.save_capsule(capsule)
    
    capsules = capture.list_capsules()
    assert len(capsules) == 3

def test_cleanup(test_repo):
    """Test cleaning up old capsules."""
    capture = ContextCapture(test_repo)
    
    # Create some capsules with unique timestamps
    from datetime import datetime, timedelta
    base_time = datetime.utcnow()
    for i in range(3):
        capsule = Capsule(
            project=ProjectInfo(
                name=capture.project_root.name,
                root_path=capture.project_root,
                git_branch=capture.git_extractor.branch_name if capture.git_extractor else None,
                git_repo=capture.git_extractor.repo_name if capture.git_extractor else None
            ),
            context=capture.build_context()
        )
        capsule.metadata.timestamp = base_time + timedelta(minutes=i)
        capture.capsule_manager.save_capsule(capsule)
    
    # Clean up (all will be recent, so none should be removed)
    removed = capture.cleanup_old_capsules(days=1)
    assert removed == 0
    
    # All capsules should still be there
    capsules = capture.list_capsules()
    assert len(capsules) == 3