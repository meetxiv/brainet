"""
Real-time context analysis module.

This module provides streaming analysis of development context to generate
immediate insights about coding patterns, focus areas, and potential tasks.
"""

from typing import Dict, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, Counter

@dataclass
class CodeSession:
    """Represents a focused coding session."""
    start_time: datetime
    end_time: datetime
    main_files: List[str]
    file_patterns: Dict[str, int]  # file extension -> count
    activity_score: float
    summary: str
    work_type: str = 'unknown'  # 'debugging', 'refactoring', 'new_feature', 'bug_fixing'

@dataclass
class ContextInsight:
    """Represents an insight derived from context analysis."""
    type: str  # 'focus', 'pattern', 'suggestion', 'alert'
    title: str
    description: str
    timestamp: datetime
    priority: int  # 1-5, higher is more important
    related_files: List[str]

class ContextAnalyzer:
    """Analyzes development context in real-time."""
    
    def __init__(self, project_root: Path):
        """Initialize the context analyzer."""
        self.project_root = project_root
        self.current_session = None
        self.recent_insights: List[ContextInsight] = []
        self.file_patterns: Dict[str, Set[str]] = defaultdict(set)
        self.session_history: List[CodeSession] = []
        self.work_patterns: Counter = Counter()
        
        # Analysis thresholds
        self.focus_threshold = timedelta(minutes=15)
        self.max_insights = 50
        self.session_gap = timedelta(minutes=30)
        self.context_switch_threshold = timedelta(minutes=10)
    
    def analyze_file_change(self, path: Path, change_type: str, diff: Optional[str] = None) -> Optional[ContextInsight]:
        """
        Analyze a file change event.
        
        Args:
            path: The changed file path
            change_type: Type of change (created, modified, deleted, moved)
            diff: Optional diff content for modified files
            
        Returns:
            Optional[ContextInsight]: An insight if one was generated
        """
        ext = path.suffix
        relative_path = str(path.relative_to(self.project_root))
        
        # Track file pattern
        self.file_patterns[ext].add(relative_path)
        
        # Analyze file patterns
        if len(self.file_patterns[ext]) >= 3:
            return ContextInsight(
                type='pattern',
                title=f'Active {ext} Development',
                description=f'You are focusing on {ext} files. Recent files: ' + 
                          ', '.join(list(self.file_patterns[ext])[-3:]),
                timestamp=datetime.now(),
                priority=3,
                related_files=list(self.file_patterns[ext])
            )
        
        # Analyze diff for significant changes
        if diff and len(diff.splitlines()) > 20:
            return ContextInsight(
                type='focus',
                title='Significant Changes',
                description=f'Large changes detected in {relative_path}',
                timestamp=datetime.now(),
                priority=4,
                related_files=[relative_path]
            )
        
        return None
    
    def analyze_session(self, 
                       active_files: List[Dict],
                       start_time: datetime,
                       end_time: datetime) -> CodeSession:
        """
        Analyze a coding session.
        
        Args:
            active_files: List of file info dicts with activity metrics
            start_time: Session start time
            end_time: Session end time
            
        Returns:
            CodeSession: Analysis of the coding session
        """
        # Sort files by activity (filter out files with errors)
        valid_files = [f for f in active_files if 'activity' in f]
        sorted_files = sorted(
            valid_files,
            key=lambda x: (x['activity']['edit_count'], x['activity']['time_spent']),
            reverse=True
        )
        
        if not sorted_files:
            # No active files with activity data
            return CodeSession(
                start_time=start_time,
                end_time=end_time,
                main_files=[],
                file_patterns={},
                activity_score=0,
                summary="No active files detected in this session."
            )
        
        # Get file patterns
        patterns = defaultdict(int)
        for file in sorted_files:
            ext = Path(file['path']).suffix
            patterns[ext] += 1
        
        # Calculate activity score (0-100)
        total_time = sum(f['activity']['time_spent'] for f in valid_files)
        total_edits = sum(f['activity']['edit_count'] for f in valid_files)
        activity_score = min(100, (total_edits * 10) + (total_time / 60))
        
        # Generate summary
        main_files = [f['path'] for f in sorted_files[:3]]
        summary = (f"Focused on {len(active_files)} files "
                  f"({', '.join(ext for ext, count in patterns.items())}). "
                  f"Most active: {', '.join(main_files)}")
        
        return CodeSession(
            start_time=start_time,
            end_time=end_time,
            main_files=main_files,
            file_patterns=dict(patterns),
            activity_score=activity_score,
            summary=summary
        )
    
    def get_current_insights(self, limit: int = 5) -> List[ContextInsight]:
        """Get recent insights, sorted by priority."""
        return sorted(
            self.recent_insights[-limit:],
            key=lambda x: (x.priority, x.timestamp),
            reverse=True
        )
    
    def analyze_workflow(self, sessions: List[CodeSession]) -> List[ContextInsight]:
        """
        Analyze workflow patterns across sessions.
        
        Args:
            sessions: List of coding sessions to analyze
            
        Returns:
            List[ContextInsight]: Workflow insights
        """
        insights = []
        
        if not sessions:
            return insights
        
        # Analyze file patterns
        all_patterns = defaultdict(int)
        work_types = []
        all_files = []
        
        for session in sessions:
            for ext, count in session.file_patterns.items():
                all_patterns[ext] += count
            if hasattr(session, 'work_type'):
                work_types.append(session.work_type)
            all_files.extend(session.main_files)
        
        # Find primary file types
        main_types = sorted(
            all_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        if main_types:
            insights.append(ContextInsight(
                type='pattern',
                title='Primary Development Focus',
                description=f'Main file types: {", ".join(f"{ext} ({count})" for ext, count in main_types)}',
                timestamp=datetime.now(),
                priority=3,
                related_files=[]
            ))
        
        # Analyze work type patterns
        if work_types:
            work_type_counter = Counter(work_types)
            most_common_work = work_type_counter.most_common(1)[0]
            if most_common_work[1] > 1:
                insights.append(ContextInsight(
                    type='pattern',
                    title='Work Pattern Detected',
                    description=f'Primary activity: {most_common_work[0]} ({most_common_work[1]} sessions)',
                    timestamp=datetime.now(),
                    priority=4,
                    related_files=list(set(all_files[:5]))
                ))
        
        # Detect context switches
        if len(sessions) >= 2:
            for i in range(1, len(sessions)):
                prev_files = sessions[i-1].main_files
                curr_files = sessions[i].main_files
                if self.detect_context_switch(curr_files, prev_files):
                    insights.append(ContextInsight(
                        type='context_switch',
                        title='Context Switch Detected',
                        description=f'Switched from {prev_files[0] if prev_files else "unknown"} to {curr_files[0] if curr_files else "unknown"}',
                        timestamp=sessions[i].start_time,
                        priority=3,
                        related_files=curr_files[:3]
                    ))
        
        # Analyze session patterns
        if len(sessions) >= 2:
            avg_score = sum(s.activity_score for s in sessions) / len(sessions)
            if avg_score > 80:
                insights.append(ContextInsight(
                    type='focus',
                    title='High Focus Sessions',
                    description='You maintain consistently high focus across sessions',
                    timestamp=datetime.now(),
                    priority=4,
                    related_files=[]
                ))
        
        return insights
    
    def add_insight(self, insight: ContextInsight):
        """Add a new insight and maintain size limit."""
        self.recent_insights.append(insight)
        if len(self.recent_insights) > self.max_insights:
            self.recent_insights = self.recent_insights[-self.max_insights:]
    
    def detect_work_pattern(self, file_changes: List[Dict], commands: List[Dict], todos: List[Dict]) -> str:
        """
        Detect work pattern type based on file changes and commands.
        
        Args:
            file_changes: List of file change information
            commands: List of command entries
            todos: List of TODO items
            
        Returns:
            Work pattern: 'debugging', 'refactoring', 'new_feature', 'bug_fixing', 'testing'
        """
        # Analyze commands
        test_commands = sum(1 for cmd in commands if 'test' in cmd.get('command', '').lower() or 'pytest' in cmd.get('command', '').lower())
        git_commands = sum(1 for cmd in commands if 'git' in cmd.get('command', '').lower())
        
        # Check for debugging patterns
        debug_keywords = ['print(', 'console.log', 'debugger', 'breakpoint', 'pdb']
        has_debug = any(keyword in str(file_changes) for keyword in debug_keywords)
        
        # Check for refactoring (similar additions/deletions, class/function renames)
        refactor_keywords = ['rename', 'extract', 'move', 'refactor']
        has_refactor = any(keyword in str(file_changes).lower() for keyword in refactor_keywords)
        
        # Check for new feature (more adds than deletes, new files)
        new_file_count = sum(1 for f in file_changes if f.get('status') == 'added')
        
        # Determine pattern
        if test_commands > 3 or has_debug:
            return 'debugging'
        elif has_refactor:
            return 'refactoring'
        elif new_file_count > 0:
            return 'new_feature'
        elif len(todos) > 5:
            return 'bug_fixing'
        elif test_commands > 0:
            return 'testing'
        else:
            return 'development'
    
    def detect_context_switch(self, current_files: List[str], previous_files: List[str]) -> bool:
        """
        Detect if user switched context between sessions.
        
        Args:
            current_files: Current session file list
            previous_files: Previous session file list
            
        Returns:
            True if context switch detected
        """
        if not previous_files:
            return False
        
        # Check file overlap
        current_set = set(current_files)
        previous_set = set(previous_files)
        overlap = len(current_set & previous_set) / max(len(current_set), len(previous_set))
        
        # Less than 30% overlap suggests context switch
        return overlap < 0.3
    
    def generate_focus_insight(self, file_path: str, duration: float, edit_count: int) -> ContextInsight:
        """Generate insight about focused work on a file."""
        if duration > 900:  # 15+ minutes
            return ContextInsight(
                type='focus',
                title='Deep Focus Detected',
                description=f'You spent {int(duration/60)} minutes on {file_path} with {edit_count} edits',
                timestamp=datetime.now(),
                priority=4,
                related_files=[file_path]
            )
        return None
        self.recent_insights.append(insight)
        if len(self.recent_insights) > self.max_insights:
            self.recent_insights = self.recent_insights[-self.max_insights:]