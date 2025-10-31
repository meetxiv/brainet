"""Tests for the terminal tracking module."""

import pytest
from datetime import datetime, timedelta
from brainet.monitor.terminal_tracker import TerminalTracker, TerminalSession

def test_terminal_session_initialization():
    """Test TerminalSession initialization."""
    session = TerminalSession("test_session")
    assert session.session_id == "test_session"
    assert isinstance(session.start_time, datetime)
    assert len(session.commands) == 0

def test_command_recording():
    """Test recording commands in a session."""
    session = TerminalSession("test_session")
    
    # Record some commands
    session.record_command("ls -l", 0)
    session.record_command("git status", 0)
    
    assert len(session.commands) == 2
    assert session.commands[0]["command"] == "ls -l"
    assert session.commands[1]["command"] == "git status"

def test_tracker_session_management():
    """Test terminal tracker session management."""
    tracker = TerminalTracker()
    
    # Start a session
    session = tracker.start_session("test_session")
    assert "test_session" in tracker.sessions
    
    # End the session
    tracker.end_session("test_session")
    assert "test_session" not in tracker.sessions

def test_command_tracking():
    """Test command tracking across sessions."""
    tracker = TerminalTracker()
    
    # Track commands in different sessions
    tracker.track_command("ls -l", "session1")
    tracker.track_command("pwd", "session1")
    tracker.track_command("git status", "session2")
    
    # Check session1
    context1 = tracker.get_session_context("session1")
    assert len(context1["recent_commands"]) == 2
    assert context1["command_count"] == 2
    
    # Check session2
    context2 = tracker.get_session_context("session2")
    assert len(context2["recent_commands"]) == 1
    assert context2["command_count"] == 1

def test_session_context():
    """Test getting session context information."""
    tracker = TerminalTracker()
    
    # Create session with some activity
    tracker.track_command("ls -l", "test_session")
    tracker.track_command("git status", "test_session")
    
    # Get context
    context = tracker.get_session_context("test_session")
    
    assert context["session_id"] == "test_session"
    assert isinstance(context["start_time"], datetime)
    assert isinstance(context["last_activity"], datetime)
    assert context["command_count"] == 2
    assert len(context["recent_commands"]) == 2

def test_default_session():
    """Test automatic default session creation."""
    tracker = TerminalTracker()
    
    # Track command without specifying session
    tracker.track_command("ls -l")
    
    # Should create and use default session
    context = tracker.get_session_context()
    assert context is not None
    assert len(context["recent_commands"]) == 1

def test_all_sessions():
    """Test retrieving all session contexts."""
    tracker = TerminalTracker()
    
    # Create multiple sessions
    tracker.track_command("cmd1", "session1")
    tracker.track_command("cmd2", "session2")
    tracker.track_command("cmd3", "session3")
    
    # Get all sessions
    sessions = tracker.get_all_sessions()
    assert len(sessions) == 3