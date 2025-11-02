"""
Code analysis modules for brainet.

This package provides intelligent code analysis capabilities through 5 sources:

Source #2: File Scanner - Loads complete file content
Source #3: AST Parser - Semantic code understanding  
Source #4: Semantic Searcher - Query-driven code discovery
Source #5: Project Context - Project structure and dependencies

(Source #1 is Git Diff in extractors/git_extractor.py)
"""

from .ast_parser import ASTParser
from .file_scanner import FileScanner
from .semantic_searcher import SemanticSearcher
from .project_context import ProjectContext

__all__ = ['ASTParser', 'FileScanner', 'SemanticSearcher', 'ProjectContext']
