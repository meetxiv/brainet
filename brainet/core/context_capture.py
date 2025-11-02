"""
Context capture orchestrator - extracts and analyzes development state.

Coordinates all 5 sources to build comprehensive context snapshots:
1. Git Diff (changes)
2. Full File Content (complete code)
3. AST Structure (code semantics)
4. Semantic Search (query-driven discovery)
5. Project Context (dependencies & structure)
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .extractors.git_extractor import GitExtractor
from .extractors.todo_extractor import TodoExtractor
from .extractors.file_extractor import FileExtractor
from .analysis.context_analyzer import ContextAnalyzer, ContextInsight

# Import all 5-source modules
from .analysis.ast_parser import ASTParser
from .analysis.file_scanner import FileScanner
from .analysis.semantic_searcher import SemanticSearcher
from .analysis.project_context import ProjectContext

from ..storage.models.capsule import (
    Capsule, ProjectInfo, ContextData, CapsuleMetadata, 
    Insight, Command, Todo, FileDiff, CodeSnippet, WorkSession
)
from ..storage.capsule_manager import CapsuleManager

class ContextCapture:
    """Orchestrates development context capture and analysis."""
    
    def __init__(self, project_root: Path):
        """Initialize all 5 context sources.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.session_start = datetime.now()  # Track session start time
        
        # Initialize extractors (legacy sources)
        self.git_extractor = GitExtractor(project_root)
        self.todo_extractor = TodoExtractor(project_root)
        self.file_extractor = FileExtractor(project_root)
        
        # Initialize 5-source architecture components
        self.ast_parser = ASTParser()
        self.file_scanner = FileScanner(project_root)
        self.semantic_searcher = SemanticSearcher(project_root, self.ast_parser, self.file_scanner)
        self.project_context = ProjectContext(project_root)
        
        # Initialize analyzer and capsule manager
        self.analyzer = ContextAnalyzer(project_root)
        capsules_dir = project_root / '.brainet' / 'capsules'
        self.capsule_manager = CapsuleManager(capsules_dir)
    
    def start_monitoring(self):
        self.file_extractor.start()
    
    def stop_monitoring(self):
        self.file_extractor.stop()
    
    def build_context(self) -> ContextData:
        return ContextData(
            modified_files=self.git_extractor.get_modified_files() if self.git_extractor else [],
            recent_commits=self.git_extractor.get_recent_commits() if self.git_extractor else [],
            todos=self.todo_extractor.extract_todos(),
            active_file=str(self.file_extractor.active_file.relative_to(self.project_root))
            if self.file_extractor.active_file else None,
            insights=[],
            recent_commands=[]
        )

    def capture_context(self) -> Capsule:
        """
        Create an immutable snapshot using ALL 5 SOURCES.
        
        Orchestrates:
        1. Git Diff Source - Extracts staged changes with AST-based smart chunking  
        2. Full File Source - Loads complete content of changed/relevant files
        3. AST Structure Source - Analyzes code structure and entities
        4. Semantic Search Source - Finds related code based on change context
        5. Project Context Source - Captures dependencies and project metadata
        
        Returns:
            Capsule: The captured context capsule with comprehensive data
        """
        # Create project info
        project_info = ProjectInfo(
            name=self.project_root.name,
            root_path=self.project_root,
            git_branch=self.git_extractor.branch_name if self.git_extractor else None,
            git_repo=self.git_extractor.repo_name if self.git_extractor else None
        )
        
        # ============================================================
        # SOURCE 1: GIT DIFF - Extract staged changes (with smart chunking)
        # ============================================================
        from ..core.config import MAX_FILES_TO_ANALYZE
        
        if self.git_extractor:
            staged_files_data = self.git_extractor.get_staged_files_with_diffs()
            
            # Convert to ModifiedFile format
            from ..storage.models.capsule import ModifiedFile
            modified_files = []
            for staged in staged_files_data[:MAX_FILES_TO_ANALYZE]:
                modified_files.append(ModifiedFile(
                    path=staged['path'],
                    status=staged['status'],
                    last_modified=datetime.now()
                ))
        else:
            modified_files = []
            staged_files_data = []
        
        file_diffs = []
        incomplete_functions = []
        all_changed_entities = []  # Track changed functions/classes across all files
        
        for i, mf in enumerate(modified_files):
            # Get diff from staged_files_data (already fetched with smart chunking)
            diff_content = staged_files_data[i].get('diff', '') if i < len(staged_files_data) else ""
            
            if diff_content is None:
                diff_content = ""
            
            # Extract modified functions using AST parser
            full_path = self.project_root / mf.path
            modified_funcs = []
            try:
                if full_path.exists() and str(full_path).endswith('.py'):
                    file_ast = self.ast_parser.parse_file(full_path)
                    if file_ast:
                        # Parse changed line numbers from diff
                        changed_lines = self._parse_changed_lines(diff_content)
                        changed_entities = file_ast.find_changed_entities(changed_lines)
                        all_changed_entities.extend(changed_entities)
                        
                        # Convert to dict format for compatibility
                        for entity_name in changed_entities:
                            # Find the entity details
                            for func in file_ast.functions:
                                if func.name == entity_name:
                                    modified_funcs.append({
                                        'name': func.name,
                                        'line_start': func.line_start,
                                        'line_end': func.line_end
                                    })
                                    break
                            for cls in file_ast.classes:
                                if cls.name == entity_name:
                                    modified_funcs.append({
                                        'name': cls.name,
                                        'line_start': cls.line_start,
                                        'line_end': cls.line_end,
                                        'class_name': cls.name
                                    })
                                    break
            except Exception as e:
                # Fallback to old extraction method
                modified_funcs = self.file_extractor.extract_modified_functions(full_path) if full_path.exists() else []
            
            # Detect change pattern
            change_pattern = self.file_extractor.detect_change_pattern(diff_content)
            
            # Count additions and deletions properly
            additions = 0
            deletions = 0
            for line in diff_content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    additions += 1
                elif line.startswith('-') and not line.startswith('---'):
                    deletions += 1
            
            file_diffs.append(FileDiff(
                file_path=mf.path,
                change_type=change_pattern,
                diff=diff_content,  # Now includes smart chunking from git_extractor
                modified_functions=modified_funcs,
                additions=additions,
                deletions=deletions
            ))
            
            # Check for incomplete functions (TODOs in modified functions)
            for func in modified_funcs:
                func_start = func.get('line_start', 0)
                func_end = func.get('line_end', 0)
                
                if func_start and func_end:
                    snippet_content = self.git_extractor.get_file_content_snippet(
                        mf.path, func_start, func_end
                    ) if self.git_extractor else ""
                    
                    is_incomplete = 'TODO' in snippet_content or 'FIXME' in snippet_content
                    
                    if is_incomplete:
                        incomplete_functions.append(CodeSnippet(
                            file_path=mf.path,
                            function_name=func.get('name'),
                            class_name=func.get('class_name'),
                            line_start=func_start,
                            line_end=func_end,
                            content=snippet_content[:1000],
                            is_incomplete=True
                        ))
        
        # ============================================================
        # SOURCE 2: FULL FILE CONTENT - Load complete files
        # ============================================================
        # SOURCE 2: FULL FILE CONTENT - Load complete files
        # ============================================================
        files_to_load = set([mf.path for mf in modified_files])  # Start with modified files
        
        # Also load files that might be related based on imports/dependencies
        for mf in modified_files:
            try:
                full_path = self.project_root / mf.path
                if full_path.exists() and str(full_path).endswith('.py'):
                    file_ast = self.ast_parser.parse_file(full_path)
                    if file_ast and file_ast.imports:
                        # Add imported local modules to loading list
                        for imp in file_ast.imports[:5]:  # Limit to top 5 imports
                            if not imp.startswith('.'):  # Skip relative imports
                                # Try to resolve import to file path
                                potential_path = imp.replace('.', '/') + '.py'
                                if (self.project_root / potential_path).exists():
                                    files_to_load.add(potential_path)
            except Exception:
                pass
        
        # Load all relevant files with full content
        full_file_contents = {}
        try:
            loaded_files = self.file_scanner.load_modified_files(list(files_to_load))
            for path, content in loaded_files.items():
                # Count lines and estimate tokens
                lines = content.count('\n') + 1 if content else 0
                tokens = len(content.split()) if content else 0
                
                full_file_contents[path] = {
                    'content': content,
                    'lines': lines,
                    'tokens': tokens,
                    'language': 'python' if path.endswith('.py') else 'unknown',
                    'last_modified': None
                }
        except Exception as e:
            print(f"[5-Source] File Scanner warning: {e}")
            import traceback
            traceback.print_exc()
        
        # ============================================================
        # SOURCE 3: AST STRUCTURE - Analyze code semantics
        # ============================================================
        ast_analysis = {}
        for mf in modified_files:
            try:
                full_path = self.project_root / mf.path
                if full_path.exists() and str(full_path).endswith('.py'):
                    # Get file content from full_file_contents if available
                    content = None
                    if mf.path in full_file_contents:
                        content = full_file_contents[mf.path].get('content')
                    
                    if not content:
                        # Fallback: read from disk
                        content = full_path.read_text(encoding='utf-8')
                    
                    # parse_file expects string path, not Path object
                    file_ast = self.ast_parser.parse_file(str(full_path), content)
                    if file_ast and not file_ast.get('error'):
                        # AST parser returns a dict with 'classes', 'functions', etc.
                        ast_analysis[mf.path] = {
                            'functions': [
                                {
                                    'name': func.get('name'),
                                    'line_start': func.get('line_start'),
                                    'line_end': func.get('line_end'),
                                    'decorators': func.get('decorators', []),
                                    'is_async': func.get('is_async', False)
                                }
                                for func in file_ast.get('functions', [])
                            ],
                            'classes': [
                                {
                                    'name': cls.get('name'),
                                    'line_start': cls.get('line_start'),
                                    'line_end': cls.get('line_end'),
                                    'methods': [
                                        {
                                            'name': method.get('name'),
                                            'line_start': method.get('line_start'),
                                            'line_end': method.get('line_end')
                                        }
                                        for method in cls.get('methods', [])
                                    ]
                                }
                                for cls in file_ast.get('classes', [])
                            ],
                            'imports': file_ast.get('imports', []),
                            'global_variables': file_ast.get('globals', [])
                        }
            except Exception as e:
                print(f"[5-Source] AST analysis warning for {mf.path}: {e}")
        
        # ============================================================
        # SOURCE 4: SEMANTIC SEARCH - Find related code
        # ============================================================
        semantic_results = []
        if all_changed_entities:
            # Build search query from changed entity names
            search_query = ' '.join(all_changed_entities[:5])  # Top 5 changed entities
            
            try:
                results = self.semantic_searcher.search(search_query, max_results=10)
                for result in results:
                    semantic_results.append({
                        'entity_name': result.entity_name,
                        'entity_type': result.entity_type,
                        'file_path': result.file_path,
                        'line_start': result.line_start,
                        'line_end': result.line_end,
                        'relevance_score': result.relevance_score,
                        'context': result.context
                    })
            except Exception as e:
                print(f"[5-Source] Semantic search warning: {e}")
        
        # ============================================================
        # SOURCE 5: PROJECT CONTEXT - Extract project metadata
        # ============================================================
        project_metadata = None
        try:
            pm = self.project_context.extract_context()
            if pm:
                project_metadata = {
                    'project_name': pm.project_name,
                    'project_type': pm.project_type,
                    'dependencies': [
                        {'name': dep.name, 'version': dep.version, 'type': dep.type}
                        for dep in pm.dependencies
                    ],
                    'total_files': pm.total_files,
                    'total_lines': pm.total_lines,
                    'file_types': pm.file_types,
                    'config_files': pm.config_files
                }
        except Exception as e:
            print(f"[5-Source] Project context warning: {e}")
        
        # ============================================================
        # LEGACY ANALYSIS - Keep for compatibility
        # ============================================================
        
        # Extract TODOs
        raw_todos = self.todo_extractor.extract_todos()
        enhanced_todos = []
        
        for todo in raw_todos:
            enhanced_todos.append(Todo(
                file=todo.file,
                line=todo.line,
                text=todo.text,
                context=todo.context,
                function_context=getattr(todo, 'function_context', None),
                detailed_context=getattr(todo, 'detailed_context', None)
            ))
        
        # Analyze session and detect work pattern
        active_files = self.file_extractor.get_active_files()
        session = self.analyzer.analyze_session(
            active_files,
            self.session_start,
            datetime.now()
        )
        
        # Convert file changes for work pattern detection
        file_changes_data = [{'file_path': fd.file_path, 'change_type': fd.change_type, 'status': 'modified'} for fd in file_diffs]
        todos_data = [{'file': t.file, 'line': t.line, 'text': t.text} for t in enhanced_todos]
        
        work_pattern = self.analyzer.detect_work_pattern(file_changes_data, [], todos_data)
        
        # Build work session  
        focus_files = []
        if hasattr(session, 'main_files') and session.main_files:
            for item in session.main_files[:5]:
                if isinstance(item, tuple):
                    focus_files.append(item[0])
                else:
                    focus_files.append(item)
        
        work_session = WorkSession(
            work_type=work_pattern,
            start_time=self.session_start,
            end_time=datetime.now(),
            focus_files=focus_files,
            activity_score=session.activity_score,
            context_switches=0,
            focus_duration=int((datetime.now() - self.session_start).total_seconds()),
            incomplete_functions=incomplete_functions
        )
        
        # Generate insights
        insights = self.analyzer.analyze_workflow([session])
        for insight in insights:
            self.analyzer.add_insight(insight)
        
        capsule_insights = [
            Insight(
                type=insight.type,
                title=insight.title,
                description=insight.description,
                timestamp=insight.timestamp,
                priority=insight.priority,
                related_files=insight.related_files
            )
            for insight in self.analyzer.get_current_insights()
        ]
        
        # ============================================================
        # BUILD COMPREHENSIVE CONTEXT DATA WITH ALL 5 SOURCES
        # ============================================================
        
        context_data = ContextData(
            # Legacy fields (for compatibility)
            modified_files=modified_files,
            recent_commits=self.git_extractor.get_recent_commits() if self.git_extractor else [],
            todos=enhanced_todos,
            active_file=str(self.file_extractor.active_file.relative_to(self.project_root))
            if self.file_extractor.active_file else None,
            insights=capsule_insights,
            recent_commands=[],
            file_diffs=file_diffs,
            work_session=work_session,
            incomplete_work=incomplete_functions,
            ai_summary=None,  # Generated in CLI layer
            next_steps=None,  # Generated in CLI layer
            
            # NEW: 5-source architecture fields
            full_file_contents=full_file_contents,
            ast_analysis=ast_analysis,
            semantic_results=semantic_results,
            project_metadata=project_metadata
        )
        
        # Create and return capsule
        capsule = Capsule(
            project=project_info,
            context=context_data,
            metadata=CapsuleMetadata(
                timestamp=datetime.now(),
                version="0.2.0"
            )
        )
        
        return capsule
    
    def _parse_changed_lines(self, diff_content: str) -> List[int]:
        """Extract changed line numbers from diff content.
        
        Args:
            diff_content: Git diff output
            
        Returns:
            List of line numbers that were changed
        """
        changed_lines = []
        current_line = 0
        
        for line in diff_content.split('\n'):
            if line.startswith('@@'):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                parts = line.split('+')[1].split(',')[0] if '+' in line else ''
                try:
                    current_line = int(parts.strip()) if parts else 0
                except ValueError:
                    continue
            elif line.startswith('+') and not line.startswith('+++'):
                # Added line
                changed_lines.append(current_line)
                current_line += 1
            elif line.startswith('-') and not line.startswith('---'):
                # Deleted line (don't increment current_line)
                pass
            elif not line.startswith('\\'):
                # Context line
                current_line += 1
        
        return changed_lines
        
    def get_recent_insights(self, limit: int = 5) -> List[ContextInsight]:
        return self.analyzer.get_current_insights(limit)
    
    def get_latest_context(self) -> Optional[Capsule]:
        return self.capsule_manager.get_latest_capsule()
    
    def list_capsules(self):
        return self.capsule_manager.list_capsules()
    
    def cleanup_old_capsules(self, days: int = 7) -> int:
        from datetime import timedelta
        return self.capsule_manager.cleanup_old_capsules(timedelta(days=days))