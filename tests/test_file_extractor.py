"""Tests for the file extractor module."""

import pytest
import time
from pathlib import Path
from brainet.core.extractors.file_extractor import FileExtractor

def test_file_extractor_initialization(test_repo):
    """Test FileExtractor initialization."""
    extractor = FileExtractor(test_repo)
    assert extractor.root_path == test_repo
    assert not extractor._started

def test_file_monitoring(test_repo):
    """Test file change monitoring."""
    extractor = FileExtractor(test_repo)
    extractor.start()
    
    try:
        # Create a new file
        new_file = test_repo / "monitored.py"
        new_file.write_text("print('hello')")
        
        # Give the observer time to detect the change
        time.sleep(0.1)
        
        assert new_file in extractor.modified_files
        assert extractor.active_file == new_file
        
        # Modify the file
        new_file.write_text("print('updated')")
        time.sleep(0.1)
        
        assert new_file in extractor.modified_files
        assert extractor.active_file == new_file
    finally:
        extractor.stop()

def test_clear_history(test_repo):
    """Test clearing file history."""
    extractor = FileExtractor(test_repo)
    extractor.start()
    
    try:
        # Create some file changes
        new_file = test_repo / "test_clear.py"
        new_file.write_text("print('hello')")
        time.sleep(0.1)
        
        assert len(extractor.modified_files) > 0
        assert extractor.active_file is not None
        
        # Clear history
        extractor.clear_history()
        
        assert len(extractor.modified_files) == 0
        assert extractor.active_file is None
    finally:
        extractor.stop()

def test_get_file_info(test_repo):
    """Test getting file information."""
    extractor = FileExtractor(test_repo)
    
    # Create a test file
    test_file = test_repo / "info_test.py"
    test_file.write_text("print('test')")
    
    info = extractor.get_file_info(test_file)
    
    assert info["path"] == "info_test.py"
    assert info["size"] > 0
    assert "last_modified" in info
    assert "created" in info

def test_stop_monitoring(test_repo):
    """Test stopping file monitoring."""
    extractor = FileExtractor(test_repo)
    extractor.start()
    assert extractor._started
    
    extractor.stop()
    assert not extractor._started