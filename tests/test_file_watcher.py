"""Tests for the file system monitoring module."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from brainet.monitor.file_watcher import FileSystemMonitor, FileChangeHandler

@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def test_file_monitor_initialization(temp_project):
    """Test FileSystemMonitor initialization."""
    monitor = FileSystemMonitor(temp_project)
    assert monitor.project_root == temp_project
    assert not monitor.is_active()

def test_start_stop_monitoring(temp_project):
    """Test starting and stopping file monitoring."""
    monitor = FileSystemMonitor(temp_project)
    
    # Start monitoring
    monitor.start()
    assert monitor.is_active()
    
    # Stop monitoring
    monitor.stop()
    assert not monitor.is_active()

def test_file_change_detection(temp_project):
    """Test file change event detection."""
    monitor = FileSystemMonitor(temp_project)
    callback = Mock()
    monitor.add_callback(callback)
    
    # Start monitoring
    monitor.start()
    
    try:
        # Create a Python file
        test_file = temp_project / "test.py"
        test_file.write_text("print('hello')")
        
        # Give the observer time to detect changes
        import time
        time.sleep(1)
        
        # Verify callback was called
        callback.assert_called()
        args = callback.call_args[0]
        assert args[0] in ("created", "modified")  # Event type can be either depending on OS/timing
        # macOS prefixes /private to temp paths - normalize for comparison
        assert Path(args[1]).resolve() == test_file.resolve()  # File path
        
    finally:
        monitor.stop()

def test_ignore_patterns(temp_project):
    """Test that ignored paths are skipped."""
    monitor = FileSystemMonitor(temp_project)
    callback = Mock()
    monitor.add_callback(callback)
    
    # Start monitoring
    monitor.start()
    
    try:
        # Create ignored directories
        (temp_project / ".git").mkdir()
        (temp_project / "__pycache__").mkdir()
        
        # Create files in ignored directories
        (temp_project / ".git" / "config").write_text("git config")
        (temp_project / "__pycache__" / "test.pyc").write_text("cache")
        
        # Give the observer time to detect changes
        import time
        time.sleep(1)
        
        # Verify callback was not called for ignored files
        assert not callback.called
        
    finally:
        monitor.stop()

def test_file_handler_patterns():
    """Test file pattern matching."""
    handler = FileChangeHandler()
    
    # Test watched patterns
    assert handler.should_process("test.py")
    assert handler.should_process("src/app.js")
    assert handler.should_process("config.json")
    assert not handler.should_process("image.png")
    
    # Test ignore patterns
    assert not handler.should_process(".git/config")
    assert not handler.should_process("__pycache__/module.pyc")
    assert not handler.should_process("node_modules/package/index.js")