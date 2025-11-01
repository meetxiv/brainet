"""
Context capture orchestrator - extracts and analyzes development state.

Coordinates extractors (Git, files, TODOs), analyzes patterns, and assembles
immutable context snapshots (Capsules).
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .extractors.git_extractor import GitExtractor
from .extractors.todo_extractor import TodoExtractor
from .extractors.file_extractor import FileExtractor
from .analysis.context_analyzer import ContextAnalyzer, ContextInsight
from ..storage.models.capsule import (
    Capsule, ProjectInfo, ContextData, CapsuleMetadata, 
    Insight, Command, Todo, FileDiff, CodeSnippet, WorkSession
)
from ..storage.capsule_manager import CapsuleManager

class ContextCapture:
    """Orchestrates development context capture and analysis."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.storage_dir = project_root / '.brainet' / 'capsules'
        
        self.git_extractor = GitExtractor(project_root) if GitExtractor.is_git_repo(project_root) else None
        self.todo_extractor = TodoExtractor(project_root)
        self.file_extractor = FileExtractor(project_root)
        
        self.analyzer = ContextAnalyzer(project_root)
        self.capsule_manager = CapsuleManager(self.storage_dir)
        
        self.session_start = datetime.now()
    
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
        Create an immutable snapshot of current development context.
        
        This is the main entry point for capturing state. It:
        1. Extracts data from all sources (git, files, todos, commands)
        2. Runs analysis to identify patterns and focus areas
        3. Assembles everything into a Capsule model
        4. Does NOT persist (caller's responsibility)
        
        Returns:
            Capsule: The captured context capsule with AI summary
        """
        # Create project info
        project_info = ProjectInfo(
            name=self.project_root.name,
            root_path=self.project_root,
            git_branch=self.git_extractor.branch_name if self.git_extractor else None,
            git_repo=self.git_extractor.repo_name if self.git_extractor else None
        )
        
        # Extract file changes with diffs (STAGED ONLY for current session)
        from ..core.config import MAX_FILES_TO_ANALYZE
        
        # Get ONLY staged files to avoid historical noise
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
        
        file_diffs = []
        incomplete_functions = []
        
        for i, mf in enumerate(modified_files):
            # Get diff from staged_files_data (already fetched)
            diff_content = staged_files_data[i].get('diff', '') if self.git_extractor and i < len(staged_files_data) else ""
            
            if diff_content is None:
                diff_content = ""
            
            # Extract modified functions
            full_path = self.project_root / mf.path
            modified_funcs = self.file_extractor.extract_modified_functions(full_path) if full_path.exists() else []
            
            # Detect change pattern
            change_pattern = self.file_extractor.detect_change_pattern(diff_content)
            
            file_diffs.append(FileDiff(
                file_path=mf.path,
                change_type=change_pattern,
                diff=diff_content[:5000],  # Limit diff size
                modified_functions=modified_funcs,
                additions=diff_content.count('\n+'),
                deletions=diff_content.count('\n-')
            ))
            
            # Check for incomplete functions (TODOs in modified functions)
            for func in modified_funcs:
                # Check if function has TODO comments
                func_start = func.get('line_start', 0)
                func_end = func.get('line_end', 0)
                
                if func_start and func_end:
                    snippet_content = self.git_extractor.get_file_content_snippet(
                        mf.path, func_start, func_end
                    ) if self.git_extractor else ""
                    
                    # Mark as incomplete if it has TODO or is very recent
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
        
        # Extract TODOs with enhanced context
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
            # main_files is a list of tuples or just strings
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
            context_switches=0,  # Can be enhanced later
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
        
        # Generate AI summary
        commits_data = [
            {'hash': c['hash'], 'message': c['message']}
            for c in (self.git_extractor.get_recent_commits() if self.git_extractor else [])
        ]
        
        file_diffs_data = [
            {
                'file_path': fd.file_path,
                'change_type': fd.change_type,
                'diff': fd.diff,
                'modified_functions': fd.modified_functions
            }
            for fd in file_diffs
        ]
        
        # AI summaries are now generated in CLI layer, not here
        ai_summary = None
        next_steps = None
        incomplete_work = None
        
        # Build context data
        context_data = ContextData(
            modified_files=modified_files,
            recent_commits=self.git_extractor.get_recent_commits() if self.git_extractor else [],
            todos=enhanced_todos,
            active_file=str(self.file_extractor.active_file.relative_to(self.project_root))
            if self.file_extractor.active_file else None,
            insights=capsule_insights,
            recent_commands=[],  # No longer tracking commands
            file_diffs=file_diffs,
            work_session=work_session,
            incomplete_work=incomplete_functions,
            ai_summary=ai_summary,
            next_steps=next_steps
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
        
    def get_recent_insights(self, limit: int = 5) -> List[ContextInsight]:
        return self.analyzer.get_current_insights(limit)
    
    def get_latest_context(self) -> Optional[Capsule]:
        return self.capsule_manager.get_latest_capsule()
    
    def list_capsules(self):
        return self.capsule_manager.list_capsules()
    
    def cleanup_old_capsules(self, days: int = 7) -> int:
        from datetime import timedelta
        return self.capsule_manager.cleanup_old_capsules(timedelta(days=days))