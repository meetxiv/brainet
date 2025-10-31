"""Tests for the TODO extractor module."""

import pytest
from pathlib import Path
from brainet.core.extractors.todo_extractor import TodoExtractor

def test_todo_extraction(test_repo):
    """Test extracting TODOs from files."""
    extractor = TodoExtractor(test_repo)
    todos = extractor.extract_todos()
    
    assert len(todos) == 3  # test.py, main.py, and src/helper.py
    assert any(t.file == "test.py" and t.text == "implement this" for t in todos)
    assert any(t.file == "main.py" and t.text == "add error handling" for t in todos)
    assert any(t.file == "src/helper.py" and t.text == "add helper functions" for t in todos)

def test_todo_line_numbers(test_repo):
    """Test that TODO line numbers are correct."""
    extractor = TodoExtractor(test_repo)
    todos = extractor.extract_todos()
    
    todo_map = {t.file: t.line for t in todos}
    assert todo_map["test.py"] == 1
    assert todo_map["main.py"] == 2

def test_todo_context(test_repo):
    """Test that TODO context is captured correctly."""
    extractor = TodoExtractor(test_repo)
    todos = extractor.extract_todos()
    
    for todo in todos:
        assert todo.context
        assert "# TODO" in todo.context or "# FIXME" in todo.context
        assert len(todo.context.splitlines()) >= 3  # Should include surrounding lines

def test_ignore_patterns(test_repo):
    """Test that ignored files are skipped."""
    # Create directories and files that should be ignored
    git_dir = test_repo / ".git"
    git_dir.mkdir(exist_ok=True)
    pycache_dir = test_repo / "__pycache__"
    pycache_dir.mkdir(exist_ok=True)
    
    # Create files that should be ignored
    (git_dir / "test.txt").write_text("# TODO: ignored")
    (pycache_dir / "test.pyc").write_text("# TODO: ignored")
    
    extractor = TodoExtractor(test_repo)
    todos = extractor.extract_todos()
    
    # Should only find the TODOs from test.py and main.py
    assert len(todos) == 3  # test.py, main.py, and src/helper.py
    assert all(not t.file.startswith(".git/") for t in todos)
    assert all(not t.file.startswith("__pycache__/") for t in todos)