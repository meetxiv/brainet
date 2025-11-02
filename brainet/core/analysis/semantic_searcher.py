"""
Semantic Searcher Module - Source #4

Provides query-driven code discovery by searching for relevant code based on
user's natural language questions, not just what's in git diffs.

This module:
- Extracts keywords from user queries
- Searches file content for keyword matches
- Uses AST to find matching code entities (classes/functions)
- Discovers related files through imports
- Enables proactive file loading based on query intent
"""

from pathlib import Path
from typing import List, Dict, Set, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class SearchResult:
    """Result from semantic search."""
    entity_name: str
    entity_type: str  # 'function', 'class', 'method'
    file_path: str
    line_start: int
    line_end: int
    relevance_score: float
    context: str  # Surrounding code context


class SemanticSearcher:
    """
    Search codebase semantically based on user queries.
    
    This is Source #4 in the 5-source architecture - enables query-driven discovery.
    """
    
    def __init__(self, project_root: Path, ast_parser, file_scanner):
        """
        Initialize semantic searcher.
        
        Args:
            project_root: Path to project root
            ast_parser: ASTParser instance for code structure search
            file_scanner: FileScanner instance for file content access
        """
        self.project_root = Path(project_root)
        self.ast_parser = ast_parser
        self.file_scanner = file_scanner
        self._file_content_cache = {}
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search for code entities matching the query.
        
        This is the main API method used by context_capture and CLI.
        
        Args:
            query: Natural language query or keywords
            max_results: Maximum number of results to return
            
        Returns:
            List of SearchResult objects ordered by relevance
        """
        keywords = self._extract_keywords(query)
        results = []
        
        if not keywords:
            return results
        
        # Search all Python files in project
        python_files = list(self.project_root.rglob("*.py"))
        
        for file_path in python_files:
            # Skip hidden dirs, venv, site-packages, but NOT test files (we want to search those!)
            path_str = str(file_path)
            if any(skip in path_str for skip in ['/.', '/venv/', '/site-packages/', '/__pycache__/']):
                continue
            # Skip egg-info and build dirs
            if '.egg-info' in path_str or '/build/' in path_str or '/dist/' in path_str:
                continue
            
            try:
                # Load file content
                content = self.file_scanner.load_file(str(file_path.relative_to(self.project_root)))
                if not content:
                    continue
                
                # Parse with AST
                parsed = self.ast_parser.parse_file(str(file_path.relative_to(self.project_root)), content)
                if not parsed:
                    continue
                
                # Search in functions
                for func in parsed.get('functions', []):
                    score = self._calculate_relevance(func['name'], func.get('docstring', ''), keywords)
                    if score > 0:
                        # Get context (function code)
                        context_lines = content.split('\n')[func['line_start']-1:func['line_end']]
                        context = '\n'.join(context_lines[:10])  # First 10 lines
                        
                        results.append(SearchResult(
                            entity_name=func['name'],
                            entity_type='function',
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_start=func['line_start'],
                            line_end=func['line_end'],
                            relevance_score=score,
                            context=context
                        ))
                
                # Search in classes
                for cls in parsed.get('classes', []):
                    score = self._calculate_relevance(cls['name'], cls.get('docstring', ''), keywords)
                    if score > 0:
                        context_lines = content.split('\n')[cls['line_start']-1:cls['line_end']]
                        context = '\n'.join(context_lines[:10])
                        
                        results.append(SearchResult(
                            entity_name=cls['name'],
                            entity_type='class',
                            file_path=str(file_path.relative_to(self.project_root)),
                            line_start=cls['line_start'],
                            line_end=cls['line_end'],
                            relevance_score=score,
                            context=context
                        ))
                    
                    # Search in methods
                    for method in cls.get('methods', []):
                        score = self._calculate_relevance(method['name'], method.get('docstring', ''), keywords)
                        if score > 0:
                            context_lines = content.split('\n')[method['line_start']-1:method['line_end']]
                            context = '\n'.join(context_lines[:10])
                            
                            results.append(SearchResult(
                                entity_name=f"{cls['name']}.{method['name']}",
                                entity_type='method',
                                file_path=str(file_path.relative_to(self.project_root)),
                                line_start=method['line_start'],
                                line_end=method['line_end'],
                                relevance_score=score,
                                context=context
                            ))
            
            except Exception:
                # Skip files that can't be parsed
                continue
        
        # Sort by relevance score and limit results
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:max_results]
    
    def _calculate_relevance(self, name: str, docstring: str, keywords: List[str]) -> float:
        """Calculate relevance score for an entity."""
        score = 0.0
        name_lower = name.lower()
        doc_lower = (docstring or '').lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Exact name match is highest score
            if keyword_lower == name_lower:
                score += 10.0
            # Name contains keyword
            elif keyword_lower in name_lower:
                score += 5.0
            # Docstring contains keyword
            elif keyword_lower in doc_lower:
                score += 2.0
        
        return score
    
    def search_query(self, query: str, modified_files: List[str]) -> Dict[str, Any]:
        """
        Search for code relevant to user query.
        
        Legacy method - kept for backward compatibility.
        
        Args:
            query: User's natural language question
            modified_files: Files that have changes (priority search area)
            
        Returns:
            {
                "query": str,
                "keywords_extracted": [list of keywords],
                "relevant_files": [list of file paths],
                "keyword_matches": {file -> [list of matches]},
                "code_entities": [list of matching classes/functions],
                "related_files": [files discovered through imports]
            }
        """
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        
        results = {
            "query": query,
            "keywords_extracted": keywords,
            "relevant_files": [],
            "keyword_matches": {},
            "code_entities": [],
            "related_files": []
        }
        
        if not keywords:
            return results
        
        # Search in modified files first (highest priority)
        for file_path in modified_files:
            matches = self._search_file_content(file_path, keywords)
            if matches:
                results["relevant_files"].append(file_path)
                results["keyword_matches"][file_path] = matches
        
        # Search AST structures for matching code entities
        for keyword in keywords:
            ast_matches = self.ast_parser.search_by_keyword(keyword)
            for match in ast_matches:
                # Add file to relevant files if not already there
                if match["file"] not in results["relevant_files"]:
                    results["relevant_files"].append(match["file"])
                
                # Add to code entities
                results["code_entities"].append(match)
        
        # Discover related files through imports
        for file_path in results["relevant_files"][:]:  # Copy list to avoid modification during iteration
            related = self._discover_related_files(file_path)
            for related_file in related:
                if related_file not in results["related_files"]:
                    results["related_files"].append(related_file)
        
        # Deduplicate and sort
        results["relevant_files"] = list(set(results["relevant_files"]))
        results["related_files"] = list(set(results["related_files"]))
        
        return results
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from user query.
        
        Uses NLP-like techniques to identify important terms.
        
        Examples:
            "what is the tier system" -> ["tier", "system"]
            "how does authentication work" -> ["authentication", "auth"]
            "show me payment functions" -> ["payment"]
            "Player class methods" -> ["player", "class", "methods"]
        """
        # Common stop words to filter out
        stop_words = {
            'what', 'is', 'the', 'how', 'does', 'do', 'did', 'show', 'me', 
            'can', 'you', 'tell', 'explain', 'describe', 'where', 'when', 
            'why', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'in', 'on', 
            'at', 'to', 'for', 'of', 'with', 'by', 'from', 'about', 'as', 
            'into', 'like', 'through', 'after', 'before', 'between', 'under',
            'work', 'works', 'working', 'worked',
            'function', 'functions', 'method', 'methods', 'class', 'classes',
            'file', 'files', 'code', 'implement', 'implementation'
        }
        
        # Extract words (alphanumeric + underscores)
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', query.lower())
        
        # Filter stop words and very short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Add common abbreviations and variations
        expanded_keywords = []
        for kw in keywords:
            expanded_keywords.append(kw)
            
            # Add plural/singular variations
            if kw.endswith('s') and len(kw) > 3:
                # Remove 's' for singular
                expanded_keywords.append(kw[:-1])
            elif not kw.endswith('s'):
                # Add 's' for plural
                expanded_keywords.append(kw + 's')
            
            # Common abbreviations
            if kw == 'authentication':
                expanded_keywords.extend(['auth', 'login', 'signin'])
            elif kw == 'authorization':
                expanded_keywords.extend(['authz', 'permission', 'access'])
            elif kw == 'configuration':
                expanded_keywords.extend(['config', 'settings'])
            elif kw == 'database':
                expanded_keywords.extend(['db', 'storage'])
            elif kw == 'initialize':
                expanded_keywords.extend(['init', 'setup'])
            elif kw == 'calculate':
                expanded_keywords.extend(['calc', 'compute'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in expanded_keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords
    
    def _search_file_content(self, file_path: str, keywords: List[str]) -> List[Dict]:
        """
        Search a single file for keyword matches.
        
        Returns list of matches with line numbers, content, and context.
        """
        # Load file content (use cache if available)
        if file_path not in self._file_content_cache:
            content = self.file_scanner.load_file(file_path)
            if not content or content.startswith('['):  # Error message
                return []
            self._file_content_cache[file_path] = content
        else:
            content = self._file_content_cache[file_path]
        
        matches = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            
            # Check if any keyword matches this line
            for keyword in keywords:
                if keyword.lower() in line_lower:
                    # Get context (2 lines before and after)
                    context_start = max(0, i - 3)
                    context_end = min(len(lines), i + 2)
                    context_lines = lines[context_start:context_end]
                    
                    matches.append({
                        "line": i,
                        "content": line.strip(),
                        "keyword": keyword,
                        "context": '\n'.join(context_lines),
                        "match_type": self._classify_match(line, keyword)
                    })
                    break  # Only record one match per line
        
        return matches
    
    def _classify_match(self, line: str, keyword: str) -> str:
        """
        Classify what type of match this is.
        
        Returns: 'definition', 'usage', 'comment', or 'string'
        """
        line_stripped = line.strip()
        
        # Check if it's a comment
        if line_stripped.startswith('#') or line_stripped.startswith('//'):
            return 'comment'
        
        # Check if it's a docstring
        if '"""' in line or "'''" in line:
            return 'docstring'
        
        # Check if it's a definition (class/function)
        if re.match(r'^\s*(class|def|function|const|let|var)\s+\w*' + re.escape(keyword), 
                   line, re.IGNORECASE):
            return 'definition'
        
        # Check if it's an assignment
        if '=' in line and keyword in line.split('=')[0]:
            return 'assignment'
        
        # Check if it's in a string literal
        if ('"' in line or "'" in line) and any(keyword in s for s in re.findall(r'["\']([^"\']*)["\']', line)):
            return 'string'
        
        # Default: usage/reference
        return 'usage'
    
    def _discover_related_files(self, file_path: str) -> List[str]:
        """
        Given a file, find related files through imports.
        
        Returns list of file paths that this file imports or is imported by.
        """
        related_files = []
        
        # Get AST structure for this file
        if file_path in self.ast_parser.parsed_files:
            structure = self.ast_parser.parsed_files[file_path]
            imports = structure.get("imports", [])
            
            # Convert imports to file paths
            for imp in imports:
                resolved_paths = self._resolve_import_to_file(file_path, imp)
                related_files.extend(resolved_paths)
        
        # Filter to only existing files
        existing_files = []
        for rel_file in related_files:
            if (self.project_root / rel_file).exists():
                existing_files.append(rel_file)
        
        return existing_files
    
    def _resolve_import_to_file(self, current_file: str, import_info: Dict) -> List[str]:
        """
        Resolve an import statement to potential file paths.
        
        Examples:
            from brainet.core import config -> brainet/core/config.py
            import player -> player.py (same directory)
        """
        resolved = []
        current_dir = Path(current_file).parent
        
        import_type = import_info.get("type")
        
        if import_type == "import":
            # import module
            module = import_info.get("module", "")
            module_path = module.replace('.', '/')
            
            # Try various locations
            candidates = [
                f"{module_path}.py",  # Direct file
                f"{module_path}/__init__.py",  # Package
                str(current_dir / f"{module}.py"),  # Same directory
            ]
            resolved.extend(candidates)
        
        elif import_type == "from_import":
            # from module import name
            module = import_info.get("module", "")
            level = import_info.get("level", 0)
            
            if level > 0:
                # Relative import (from . import x, from .. import y)
                # Go up 'level' directories
                target_dir = current_dir
                for _ in range(level):
                    target_dir = target_dir.parent
                
                if module:
                    module_path = target_dir / module.replace('.', '/')
                else:
                    module_path = target_dir
                
                candidates = [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py"
                ]
            else:
                # Absolute import
                module_path = module.replace('.', '/')
                candidates = [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py"
                ]
            
            resolved.extend(candidates)
        
        return resolved
    
    def find_files_by_pattern(self, pattern: str) -> List[str]:
        """
        Find files matching a name pattern.
        
        Args:
            pattern: Glob pattern or simple substring
            
        Returns:
            List of matching file paths
        """
        matches = []
        
        # Search in project
        for file_path in self.project_root.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(self.project_root)
                
                # Skip ignored directories
                if any(part.startswith('.') or part in {'__pycache__', 'node_modules', 'venv'}
                      for part in relative_path.parts):
                    continue
                
                # Check if pattern matches
                if pattern.lower() in str(relative_path).lower():
                    matches.append(str(relative_path))
        
        return matches
    
    def search_in_docstrings(self, keywords: List[str]) -> List[Dict]:
        """
        Search specifically in function/class docstrings.
        
        Useful for finding functionality based on description.
        """
        matches = []
        
        for file_path, structure in self.ast_parser.parsed_files.items():
            # Search class docstrings
            for cls in structure.get("classes", []):
                docstring = cls.get("docstring", "")
                if docstring and any(kw.lower() in docstring.lower() for kw in keywords):
                    matches.append({
                        "file": file_path,
                        "type": "class",
                        "name": cls["name"],
                        "line": cls["line_start"],
                        "docstring": docstring,
                        "match_source": "docstring"
                    })
                
                # Search method docstrings
                for method in cls.get("methods", []):
                    method_doc = method.get("docstring", "")
                    if method_doc and any(kw.lower() in method_doc.lower() for kw in keywords):
                        matches.append({
                            "file": file_path,
                            "type": "method",
                            "name": f"{cls['name']}.{method['name']}",
                            "line": method["line_start"],
                            "docstring": method_doc,
                            "match_source": "docstring"
                        })
            
            # Search function docstrings
            for func in structure.get("functions", []):
                func_doc = func.get("docstring", "")
                if func_doc and any(kw.lower() in func_doc.lower() for kw in keywords):
                    matches.append({
                        "file": file_path,
                        "type": "function",
                        "name": func["name"],
                        "line": func["line_start"],
                        "docstring": func_doc,
                        "match_source": "docstring"
                    })
        
        return matches
    
    def rank_files_by_relevance(self, query: str, file_paths: List[str]) -> List[tuple]:
        """
        Rank files by relevance to query.
        
        Returns list of (file_path, score) tuples, sorted by score (descending).
        """
        keywords = self._extract_keywords(query)
        
        file_scores = []
        
        for file_path in file_paths:
            score = 0
            
            # Check filename matches
            filename = Path(file_path).name.lower()
            for kw in keywords:
                if kw.lower() in filename:
                    score += 10  # High weight for filename match
            
            # Check AST matches
            if file_path in self.ast_parser.parsed_files:
                structure = self.ast_parser.parsed_files[file_path]
                
                # Class name matches
                for cls in structure.get("classes", []):
                    if any(kw.lower() in cls["name"].lower() for kw in keywords):
                        score += 5
                
                # Function name matches
                for func in structure.get("functions", []):
                    if any(kw.lower() in func["name"].lower() for kw in keywords):
                        score += 3
            
            # Check content matches
            content_matches = self._search_file_content(file_path, keywords)
            score += len(content_matches)  # 1 point per match
            
            file_scores.append((file_path, score))
        
        # Sort by score (descending)
        file_scores.sort(key=lambda x: x[1], reverse=True)
        
        return file_scores
    
    def get_context_for_entity(self, file_path: str, entity_name: str) -> Optional[Dict]:
        """
        Get full context for a specific code entity.
        
        Returns entity info plus surrounding context.
        """
        # Get line range from AST
        line_range = self.ast_parser.get_line_range_for_entity(file_path, entity_name)
        if not line_range:
            return None
        
        # Load file content
        content = self.file_scanner.load_file(file_path)
        if not content:
            return None
        
        lines = content.split('\n')
        start_line, end_line = line_range
        
        # Extract entity code with some context
        context_start = max(0, start_line - 3)
        context_end = min(len(lines), end_line + 3)
        
        entity_code = '\n'.join(lines[start_line-1:end_line])
        full_context = '\n'.join(lines[context_start:context_end])
        
        return {
            "file": file_path,
            "entity": entity_name,
            "line_start": start_line,
            "line_end": end_line,
            "code": entity_code,
            "context": full_context
        }
    
    def clear_cache(self):
        """Clear file content cache."""
        self._file_content_cache.clear()
