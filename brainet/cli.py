"""Brainet CLI - Command-line interface for cognitive context tracking."""

try:
    import click
except ImportError:
    raise ImportError("Please install click: pip install click")

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
except ImportError:
    raise ImportError("Please install rich: pip install rich")

import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from .core.context_capture import ContextCapture
from .utils.errors import (
    handle_error, 
    NotInGitRepoError, 
    NoActiveSessionError,
    APIKeyMissingError
)

console = Console()

context_capture = None

def _find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find project root by traversing up to find .brainet/ or .git/ directory."""
    current = start_path or Path.cwd()
    
    # Traverse up the directory tree
    for parent in [current] + list(current.parents):
        # Check for .brainet directory first (brainet project)
        if (parent / ".brainet").exists():
            return parent
        # Fallback to .git directory (git project without brainet yet)
        if (parent / ".git").exists():
            return parent
    
    # If nothing found, return current directory
    return Path.cwd()

def _get_session_file() -> Path:
    """Get session file path, auto-detecting project root."""
    project_root = _find_project_root()
    return project_root / ".brainet" / "_session.json"

def _save_session_state(project_root: Path):
    session_file = _get_session_file()
    session_file.parent.mkdir(parents=True, exist_ok=True)
    with open(session_file, "w") as f:
        json.dump({"project_root": str(project_root)}, f)

def _load_session_state() -> Optional[Path]:
    session_file = _get_session_file()
    if not session_file.exists():
        return None
    try:
        with open(session_file, "r") as f:
            data = json.load(f)
            return Path(data["project_root"])
    except Exception as e:
        console.print(f"[red]Error loading session:[/red] {str(e)}")
        return None

def _clear_session_state():
    try:
        session_file = _get_session_file()
        session_file.unlink()
    except Exception as e:
        console.print(f"[red]Error clearing session:[/red] {str(e)}")
        
def _ensure_context_capture() -> Optional['ContextCapture']:
    global context_capture
    if not context_capture:
        project_root = _load_session_state()
        if project_root:
            from .core.context_capture import ContextCapture
            context_capture = ContextCapture(project_root)
            context_capture.start_monitoring()
    return context_capture

@click.group()
@click.version_option()
def main():
    pass

@main.command()
@click.option('--path', '-p', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              default='.', help='Path to the project root directory')
def start(path):
    """Initialize brainet tracking for your project."""
    try:
        global context_capture
        project_root = Path(path).resolve()
        
        # Check if git repository exists
        if not (project_root / ".git").exists():
            raise NotInGitRepoError(
                f"Directory {project_root} is not a git repository"
            )
        
        console.print("[yellow]Starting Brainet context tracking...[/yellow]")
        context_capture = ContextCapture(project_root)
        context_capture.start_monitoring()
        _save_session_state(project_root)
        console.print(f"[green]✓[/green] Context tracking initialized for {project_root.name}")
        console.print(f"\n[dim]💡 Run 'brainet capture' to save your progress[/dim]")
        
    except NotInGitRepoError as e:
        handle_error(e, "start")
    except Exception as e:
        handle_error(e, "start")

@main.command()
def pause():
    global context_capture
    
    if not context_capture:
        project_root = _load_session_state()
        if not project_root:
            console.print("[red]Error:[/red] No active context tracking session")
            return
        context_capture = ContextCapture(project_root)
    
    if not context_capture:
        console.print("[red]Error:[/red] No active context tracking session")
        return
    
    console.print("[yellow]⏸️  Pausing context tracking...[/yellow]")
    capsule = context_capture.capture_context()
    
    # AI summary generation using Groq
    from .ai.session_summarizer import SessionSummarizerSync
    
    summarizer = SessionSummarizerSync(use_ai=True)
    
    # Transform capsule model to dict format expected by summarizer
    capsule_data = {
        "git_info": {
            "current_branch": capsule.project.git_branch or "unknown",
            "uncommitted_changes": len(capsule.context.file_diffs) > 0
        },
        "file_changes": [
            {
                "path": f.file_path,
                "additions": f.additions,
                "deletions": f.deletions,
                "diff": f.diff
            }
            for f in capsule.context.file_diffs
        ],
        "todos": [
            {"file": t.file, "line": t.line, "text": t.text}
            for t in capsule.context.todos
        ]
    }
    
    # Generate AI summary and attach to capsule
    summary = summarizer.generate_summary(capsule_data)
    capsule.context.ai_summary = summary
    
    # Save to JSON storage (single source of truth)
    context_capture.capsule_manager.save_capsule(capsule)
    
    context_capture.stop_monitoring()
    rprint(Panel.fit(
        f"[green]✓[/green] Context saved\n\n"
        f"[bold white]Summary:[/bold white] {summary}\n\n"
        f"[dim]Run 'brainet resume' to continue from this point[/dim]",
        title="⏸️  Paused",
        border_style="green"
    ))

@main.command()
@click.option('--tag', '-t', multiple=True, help='Add tags to this session (e.g., --tag bugfix --tag auth)')
@click.option('--message', '-m', help='Add a custom message/note to this session')
def capture(tag, message):
    """Capture current development context with intelligent summary."""
    try:
        context_capture = _ensure_context_capture()
        if not context_capture:
            raise NoActiveSessionError("No active session found")
        
        with console.status("[yellow]📸 Capturing context...[/yellow]"):
            capsule = context_capture.capture_context()
        
        # Check if there are any changes
        if not capsule.context.file_diffs and not capsule.context.recent_commits:
            console.print("\n[yellow]⚠️  No changes detected[/yellow]")
            console.print("[dim]Make some code changes or commits first, then capture again[/dim]\n")
            return
        
        # Generate AI summary via Groq (single fast call)
        from .ai.session_summarizer import SessionSummarizerSync
        summarizer = SessionSummarizerSync(use_ai=True)
        
        # Transform capsule model to dict format for AI analysis
        capsule_data = {
            "git_info": {
                "current_branch": capsule.project.git_branch or "unknown",
                "uncommitted_changes": len(capsule.context.file_diffs) > 0
            },
            "file_changes": [
                {
                    "path": f.file_path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "diff": f.diff
                }
                for f in capsule.context.file_diffs
            ],
            "recent_commits": [
                {
                    "hash": c.hash if hasattr(c, 'hash') else c["hash"],
                    "message": c.message if hasattr(c, 'message') else c["message"],
                    "timestamp": c.timestamp.isoformat() if hasattr(c, 'timestamp') else c.get("timestamp", "")
                }
                for c in capsule.context.recent_commits
            ],
            "todos": [
                {"file": t.file, "line": t.line, "text": t.text}
                for t in capsule.context.todos
            ]
        }
        
        # Generate summary (optimized for speed - skips next_steps generation)
        summary = summarizer.generate_summary(capsule_data)
        
        # Attach AI summary and tags/message to capsule before persistence
        capsule.context.ai_summary = summary
        
        # Calculate session duration
        from datetime import datetime
        session_duration = (datetime.now() - context_capture.session_start).total_seconds()
        capsule.metadata.session_duration = session_duration
        
        # Add tags and custom message if provided
        if tag:
            capsule.metadata.tags = list(tag)
        if message:
            capsule.metadata.custom_message = message
        
        # Save to JSON storage (single source of truth)
        context_capture.capsule_manager.save_capsule(capsule)
        
        # Show clean, single output
        modified = len(capsule.context.file_diffs)
        todos = len(capsule.context.todos)
        insights = len(capsule.context.insights)
        
        # Build output with tags/message if present
        stats_text = f"[bold cyan]{summary}[/bold cyan]\n\n"
        if tag:
            tags_str = ", ".join([f"[magenta]{t}[/magenta]" for t in tag])
            stats_text += f"[dim]🏷️  Tags: {tags_str}[/dim]\n"
        if message:
            stats_text += f"[dim]💬 Note: {message}[/dim]\n"
        if tag or message:
            stats_text += "\n"
        stats_text += (
            f"[dim]📊 Stats:[/dim]\n"
            f"[dim]   • {modified} files modified[/dim]\n"
            f"[dim]   • {todos} TODOs found[/dim]\n"
        )
        
        console.print()
        rprint(Panel.fit(stats_text +
            f"\n[green]✓[/green] Capsule saved: [dim]{capsule.metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            title="📸 Context Captured",
            border_style="cyan"
        ))
        console.print(f"\n[bright_black]💡 Run [cyan]brainet ask[/cyan] to query your context with AI[/bright_black]\n")
        
    except NoActiveSessionError as e:
        handle_error(e, "capture")
    except APIKeyMissingError as e:
        handle_error(e, "capture")
    except Exception as e:
        handle_error(e, "capture")

@main.command()
def resume():
    """Resume from last saved context with intelligent analysis."""
    from .storage.capsule_manager import CapsuleManager
    from pathlib import Path
    import os
    
    project_root = Path.cwd()
    brainet_dir = project_root / ".brainet"
    capsules_dir = brainet_dir / "capsules"
    
    # Load latest capsule from JSON storage
    if not capsules_dir.exists():
        console.print("[yellow]No capsules found to resume from[/yellow]")
        return
    
    capsule_files = sorted(capsules_dir.glob("capsule_*.json"), reverse=True)
    if not capsule_files:
        console.print("[yellow]No capsules found to resume from[/yellow]")
        return
    
    import json
    with open(capsule_files[0]) as f:
        capsule_data = json.load(f)
    
    console.print("[bold cyan]🔄 Restoring your development flow...[/bold cyan]\n")
    context = capsule_data.get("context", {})
    project_info = capsule_data.get("project", {})
    metadata = capsule_data.get("metadata", {})
    
    # Extract project metadata (handles both dict and legacy string formats)
    project_name = project_info.get('name', 'unknown') if isinstance(project_info, dict) else str(project_info)
    git_branch = project_info.get('git_branch', 'N/A') if isinstance(project_info, dict) else 'N/A'
    
    # Extract AI-generated insights
    ai_summary = context.get('ai_summary')
    next_steps = context.get('next_steps')
    work_session = context.get('work_session', {})
    
    # Get modified files (handles both storage formats for backward compatibility)
    file_diffs = context.get('file_diffs', [])
    modified_files = context.get('modified_files', [])
    total_modified = len(file_diffs) if file_diffs else len(modified_files)
    
    # Get last active file from file_diffs or modified_files
    last_file = context.get('active_file')
    if not last_file and file_diffs:
        last_file = file_diffs[0].get('file_path') if isinstance(file_diffs[0], dict) else None
    if not last_file and modified_files:
        last_file = modified_files[0].get('path') if isinstance(modified_files[0], dict) else None
    
    # Session Summary Panel with AI-generated content
    summary_text = ai_summary or 'No summary available'
    work_type = work_session.get('work_type', 'unknown') if isinstance(work_session, dict) else 'unknown'
    
    rprint(Panel.fit(
        f"[bold white]Project:[/bold white] {project_name}\n"
        f"[bold white]Branch:[/bold white] {git_branch}\n"
        f"[bold white]Work Type:[/bold white] {work_type}\n"
        f"[bold white]Last Active File:[/bold white] {last_file or 'None'}\n"
        f"[bold white]Modified Files:[/bold white] {total_modified}\n"
        f"[bold white]Pending TODOs:[/bold white] {len(context.get('todos', []))}\n\n"
        f"[bold white]What You Were Doing:[/bold white]\n{summary_text}",
        title="📋 Session Summary",
        border_style="cyan"
    ))
    
    # Show Incomplete Functions (only if truly incomplete with pass/... statements)
    incomplete_work = context.get('incomplete_work', [])
    # Filter for ACTUALLY incomplete functions
    # A function is incomplete ONLY if:
    # 1. Its body contains ONLY '...' (ellipsis)
    # 2. Its body contains ONLY 'pass'
    truly_incomplete = []
    for snippet in incomplete_work:
        if not isinstance(snippet, dict):
            continue
        
        content = snippet.get('content', '')
        line_start = snippet.get('line_start', 0)
        line_end = snippet.get('line_end', 0)
        
        # Extract only the actual function lines (marked with >>>)
        lines = content.split('\n')
        function_lines = []
        for line in lines:
            # Check if this line is within the function range
            if '|' in line:
                parts = line.split('|', 1)
                line_num_str = parts[0].replace('>>>', '').strip()
                try:
                    line_num = int(line_num_str)
                    if line_start <= line_num <= line_end:
                        code = parts[1] if len(parts) > 1 else ''
                        function_lines.append(code)
                except ValueError:
                    continue
        
        # Join and analyze only the function body
        func_content = '\n'.join(function_lines)
        
        # Get code lines (skip def, docstrings, comments, blank lines)
        code_lines = []
        in_docstring = False
        for line in function_lines:
            stripped = line.strip()
            if stripped.startswith('def '):
                continue
            if '"""' in stripped or "'''" in stripped:
                in_docstring = not in_docstring
                continue
            if in_docstring or not stripped or stripped.startswith('#'):
                continue
            code_lines.append(stripped)
        
        # Function is incomplete if body is ONLY '...' or 'pass'
        if len(code_lines) == 1 and code_lines[0] in ['...', 'pass']:
            truly_incomplete.append(snippet)
    
    if truly_incomplete:
        console.print("\n[bold red]🔴 Incomplete Functions:[/bold red]")
        incomplete_table = Table(show_header=True, header_style="bold red")
        incomplete_table.add_column("File", style="yellow")
        incomplete_table.add_column("Function", style="cyan")
        incomplete_table.add_column("Lines", justify="right", style="dim")
        
        for snippet in truly_incomplete[:5]:
            file_path = snippet.get('file_path', '')[:40]
            func_name = snippet.get('function_name', 'unknown')
            class_name = snippet.get('class_name')
            line_range = f"{snippet.get('line_start', 0)}-{snippet.get('line_end', 0)}"
            
            func_display = f"{class_name}.{func_name}" if class_name else func_name
            incomplete_table.add_row(file_path, func_display, line_range)
        
        console.print(incomplete_table)
        console.print("\n[bright_black]💡 These functions are unfinished (contain 'pass' or '...'[/bright_black]")
    
    # Show Recent Commits
    recent_commits = context.get('recent_commits', [])
    if recent_commits:
        console.print("\n[bold yellow]📝 Recent Commits:[/bold yellow]")
        cmd_table = Table(show_header=True, header_style="bold magenta")
        cmd_table.add_column("Hash", style="cyan", width=10)
        cmd_table.add_column("Message", style="white")
        
        for commit in recent_commits[:5]:
            if isinstance(commit, dict):
                cmd_table.add_row(
                    commit.get('hash', '')[:7],
                    commit.get('message', '')[:60]
                )
        
        console.print(cmd_table)
    
    # Show TODOs with Function Context
    todos = context.get('todos', [])
    if todos:
        console.print("\n[bold green]✅ Unfinished Tasks (TODOs):[/bold green]")
        todo_table = Table(show_header=True, header_style="bold green")
        todo_table.add_column("File", style="yellow")
        todo_table.add_column("Location", style="cyan")
        todo_table.add_column("Task", style="white")
        
        for todo in todos[:10]:
            if isinstance(todo, dict):
                file_path = todo.get('file', '')[:30]
                line_num = str(todo.get('line', ''))
                
                # Include function context if available
                func_context = todo.get('function_context', '')
                if func_context:
                    location = f"Line {line_num} ({func_context})"
                else:
                    location = f"Line {line_num}"
                
                task_text = todo.get('text', '')[:50]
                todo_table.add_row(file_path, location, task_text)
        
        console.print(todo_table)
        
        if len(todos) > 10:
            console.print(f"\n[dim]... and {len(todos) - 10} more TODOs[/dim]")
    
    # Show AI-Generated Next Steps
    if next_steps:
        console.print("\n[bold magenta]🎯 Suggested Next Steps:[/bold magenta]")
        console.print(Panel.fit(
            next_steps,
            border_style="magenta",
            padding=(1, 2)
        ))
    
    # Show Insights / Patterns
    insights = context.get('insights', [])
    if insights:
        console.print("\n[bold magenta]💡 Workflow Insights:[/bold magenta]")
        for insight in insights[:3]:  # Show top 3 insights
            type_emoji = {
                'focus': '🎯',
                'pattern': '📊',
                'suggestion': '💡',
                'alert': '⚠️'
            }.get(insight.get('type', ''), '•')
            
            console.print(f"{type_emoji} [bold]{insight.get('title', '')}[/bold]")
            console.print(f"   {insight.get('description', '')}\n")
    
    # Next Steps Suggestion
    console.print("\n[bold white on blue] 🚀 Next Steps:[/bold white on blue]")
    if todos:
        console.print(f"  1. Continue working on TODOs in: [cyan]{todos[0].get('file', '')}[/cyan]")
    if context.get('active_file'):
        console.print(f"  2. Re-open your last active file: [cyan]{context.get('active_file')}[/cyan]")
    
    console.print("\n[dim]Run 'brainet history' to see all captured sessions[/dim]")


@main.command()
@click.option("--limit", default=10, help="Number of capsules to show")
def history(limit: int):
    """List recent capture sessions with AI summaries."""
    from pathlib import Path
    import json
    
    # Get all capsule files
    capsule_dir = Path.cwd() / ".brainet" / "capsules"
    if not capsule_dir.exists():
        console.print("[yellow]No capsules found. Run [cyan]brainet capture[/cyan] first.[/yellow]")
        return
    
    capsule_files = sorted(capsule_dir.glob("capsule_*.json"), reverse=True)[:limit]
    
    if not capsule_files:
        console.print("[yellow]No capsules found.[/yellow]")
        return
    
    console.print(f"\n[bold cyan]📚 Recent Capture Sessions ({len(capsule_files)}):[/bold cyan]\n")
    
    for i, capsule_path in enumerate(capsule_files, 1):
        try:
            with open(capsule_path, 'r') as f:
                data = json.load(f)
            
            # Get timestamp
            timestamp = data.get("metadata", {}).get("timestamp", "Unknown")
            
            # Get AI summary (handle different structures)
            context = data.get("context", {})
            ai_summary = context.get("ai_summary") or "No summary available"
            
            # Get file count
            file_diffs = context.get("file_diffs", [])
            files_count = len(file_diffs) if file_diffs else 0
            
            # Format timestamp nicely
            if timestamp != "Unknown":
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime("%b %d, %H:%M:%S")
                except:
                    time_str = timestamp
            else:
                time_str = "Unknown time"
            
            # Truncate summary if too long
            if len(ai_summary) > 120:
                ai_summary = ai_summary[:117] + "..."
            
            console.print(f"[bold yellow]{i}.[/bold yellow] [dim]{time_str}[/dim] - [cyan]{files_count} files[/cyan]")
            console.print(f"   {ai_summary}")
            console.print()
            
        except Exception as e:
            console.print(f"[dim red]  Error reading {capsule_path.name}: {e}[/dim red]")
    
    console.print(f"[dim]💡 Run [cyan]brainet ask[/cyan] to query your session with AI[/dim]\n")

@main.command()
@click.argument('query', required=True)
@click.option('--file', '-f', help='Search only in sessions that modified this file')
@click.option('--limit', '-n', type=int, default=20, help='Maximum results to show')
def search(query, file, limit):
    """Search through session history by keyword.
    
    Examples:
        brainet search "auth"           # Find sessions mentioning auth
        brainet search "bug" -f auth.py # Search in sessions that modified auth.py
        brainet search "TODO" -n 5      # Show first 5 results
    """
    context = _ensure_context_capture()
    if not context:
        console.print("[yellow]No active tracking session[/yellow]")
        return
    
    capsule_manager = context.capsule_manager
    capsules = capsule_manager.list_capsules()
    
    if not capsules:
        console.print("[yellow]No sessions to search[/yellow]")
        return
    
    console.print(f"\n[bold cyan]🔍 Searching for:[/bold cyan] '{query}'\n")
    
    import json
    from datetime import datetime
    results = []
    query_lower = query.lower()
    
    for capsule_path in capsules:
        try:
            with open(capsule_path, 'r') as f:
                data = json.load(f)
            
            context_data = data.get("context", {})
            timestamp = data.get("metadata", {}).get("timestamp", "Unknown")
            ai_summary = context_data.get("ai_summary", "")
            file_diffs = context_data.get("file_diffs", [])
            todos = context_data.get("todos", [])
            commits = context_data.get("recent_commits", [])
            
            # Check if file filter matches
            if file:
                file_paths = [fd.get('file_path', '') for fd in file_diffs]
                if not any(file in fp for fp in file_paths):
                    continue  # Skip if file not in this session
            
            # Search in various fields
            matches = []
            
            # Search in AI summary
            if query_lower in ai_summary.lower():
                matches.append(f"summary: {ai_summary[:100]}...")
            
            # Search in file paths
            for fd in file_diffs:
                file_path = fd.get('file_path', '')
                if query_lower in file_path.lower():
                    matches.append(f"file: {file_path}")
            
            # Search in TODOs
            for todo in todos:
                if query_lower in todo.get('text', '').lower():
                    matches.append(f"TODO: {todo.get('text', '')[:80]}")
            
            # Search in commit messages
            for commit in commits:
                if query_lower in commit.get('message', '').lower():
                    matches.append(f"commit: {commit.get('message', '')[:80]}")
            
            # Search in tags
            metadata = data.get("metadata", {})
            tags = metadata.get("tags", [])
            for tag in tags:
                if query_lower in tag.lower():
                    matches.append(f"tag: {tag}")
            
            # Search in custom message
            custom_message = metadata.get("custom_message", "")
            if custom_message and query_lower in custom_message.lower():
                matches.append(f"note: {custom_message}")
            
            if matches:
                results.append({
                    'timestamp': timestamp,
                    'matches': matches,
                    'file_count': len(file_diffs),
                    'summary': ai_summary
                })
        
        except Exception:
            continue
    
    if not results:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        if file:
            console.print(f"[dim]Try searching without the file filter[/dim]\n")
        return
    
    # Show results
    console.print(f"[green]Found {len(results)} session(s)[/green]\n")
    
    for i, result in enumerate(results[:limit], 1):
        timestamp = result['timestamp']
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%b %d, %H:%M:%S")
        except:
            time_str = timestamp
        
        console.print(f"[bold yellow]{i}.[/bold yellow] [dim]{time_str}[/dim] - [cyan]{result['file_count']} files[/cyan]")
        console.print(f"   [bold]{result['summary'][:100]}...[/bold]" if len(result['summary']) > 100 else f"   [bold]{result['summary']}[/bold]")
        
        # Show matches
        for match in result['matches'][:3]:  # Show first 3 matches
            console.print(f"   [green]✓[/green] {match}")
        
        if len(result['matches']) > 3:
            console.print(f"   [dim]... and {len(result['matches']) - 3} more matches[/dim]")
        
        console.print()
    
    if len(results) > limit:
        console.print(f"[dim]Showing {limit} of {len(results)} results. Use -n to show more.[/dim]\n")

@main.command()
@click.argument('session_index', type=int, required=False)
def diff(session_index):
    """Show code diffs from a session.
    
    Examples:
        brainet diff          # Show diffs from most recent session
        brainet diff 3        # Show diffs from 3rd most recent session
    """
    context = _ensure_context_capture()
    if not context:
        console.print("[yellow]No active tracking session[/yellow]")
        return
    
    capsule_manager = context.capsule_manager
    capsules = capsule_manager.list_capsules()
    
    if not capsules:
        console.print("[yellow]No sessions available[/yellow]")
        return
    
    # Default to most recent session (index 0)
    if session_index is None:
        session_index = 1
    
    # Convert to 0-based index
    idx = session_index - 1
    
    if idx < 0 or idx >= len(capsules):
        console.print(f"[red]Error:[/red] Session {session_index} not found. Use [cyan]brainet history[/cyan] to see available sessions.")
        return
    
    capsule_path = capsules[idx]
    
    import json
    from datetime import datetime
    
    try:
        with open(capsule_path, 'r') as f:
            data = json.load(f)
        
        timestamp = data.get("metadata", {}).get("timestamp", "Unknown")
        context_data = data.get("context", {})
        ai_summary = context_data.get("ai_summary", "No summary")
        file_diffs = context_data.get("file_diffs", [])
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%B %d, %Y at %H:%M:%S")
        except:
            time_str = timestamp
        
        # Show session header
        console.print()
        rprint(Panel.fit(
            f"[bold white]Session:[/bold white] #{session_index}\n"
            f"[bold white]Date:[/bold white] {time_str}\n"
            f"[bold white]Summary:[/bold white] {ai_summary}\n"
            f"[bold white]Files:[/bold white] {len(file_diffs)}",
            title="📊 Session Details",
            border_style="cyan"
        ))
        
        if not file_diffs:
            console.print("\n[yellow]No file changes in this session[/yellow]\n")
            return
        
        # Show diffs for each file
        for fd in file_diffs:
            file_path = fd.get('file_path', 'Unknown')
            additions = fd.get('additions', 0)
            deletions = fd.get('deletions', 0)
            diff = fd.get('diff', '')
            
            console.print(f"\n[bold cyan]📄 {file_path}[/bold cyan] [green]+{additions}[/green] [red]-{deletions}[/red]")
            console.print("[dim]" + "─" * 60 + "[/dim]")
            
            if diff:
                # Colorize diff output
                for line in diff.split('\n'):
                    if line.startswith('+++') or line.startswith('---'):
                        console.print(f"[bold]{line}[/bold]")
                    elif line.startswith('+'):
                        console.print(f"[green]{line}[/green]")
                    elif line.startswith('-'):
                        console.print(f"[red]{line}[/red]")
                    elif line.startswith('@@'):
                        console.print(f"[cyan]{line}[/cyan]")
                    else:
                        console.print(f"[dim]{line}[/dim]")
            else:
                console.print("[dim]No diff available[/dim]")
        
        console.print()
    
    except Exception as e:
        console.print(f"[red]Error reading session:[/red] {e}\n")

@main.command()
def stats():
    """Show session statistics and analytics.
    
    Displays:
        - Total sessions, time tracked
        - Most active files
        - Most used tags
        - Productivity patterns
    """
    context = _ensure_context_capture()
    if not context:
        console.print("[yellow]No active tracking session[/yellow]")
        return
    
    capsule_manager = context.capsule_manager
    capsules = capsule_manager.list_capsules()
    
    if not capsules:
        console.print("[yellow]No sessions to analyze[/yellow]")
        return
    
    import json
    from datetime import datetime
    from collections import Counter
    
    total_sessions = len(capsules)
    total_duration = 0
    file_counter = Counter()
    tag_counter = Counter()
    daily_sessions = Counter()
    total_files_modified = 0
    total_todos = 0
    total_additions = 0
    total_deletions = 0
    
    for capsule_path in capsules:
        try:
            with open(capsule_path, 'r') as f:
                data = json.load(f)
            
            # Duration
            metadata = data.get("metadata", {})
            duration = metadata.get("session_duration", 0)
            if duration:
                total_duration += duration
            
            # Tags
            tags = metadata.get("tags", [])
            for tag in tags:
                tag_counter[tag] += 1
            
            # Files
            context_data = data.get("context", {})
            file_diffs = context_data.get("file_diffs", [])
            for fd in file_diffs:
                file_path = fd.get('file_path', '')
                if file_path:
                    file_counter[file_path] += 1
                    total_additions += fd.get('additions', 0)
                    total_deletions += fd.get('deletions', 0)
            total_files_modified += len(file_diffs)
            
            # TODOs
            todos = context_data.get("todos", [])
            total_todos += len(todos)
            
            # Daily distribution
            timestamp = metadata.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    date_key = dt.strftime('%Y-%m-%d')
                    daily_sessions[date_key] += 1
                except:
                    pass
        
        except Exception:
            continue
    
    # Calculate averages
    avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
    avg_files_per_session = total_files_modified / total_sessions if total_sessions > 0 else 0
    
    # Display stats
    console.print()
    rprint(Panel.fit(
        f"[bold white]Total Sessions:[/bold white] {total_sessions}\n"
        f"[bold white]Total Time Tracked:[/bold white] {total_duration / 3600:.1f} hours\n"
        f"[bold white]Average Session Length:[/bold white] {avg_duration / 60:.1f} minutes\n"
        f"[bold white]Total Files Modified:[/bold white] {total_files_modified}\n"
        f"[bold white]Average Files/Session:[/bold white] {avg_files_per_session:.1f}\n"
        f"[bold white]Total Code Changes:[/bold white] [green]+{total_additions}[/green] [red]-{total_deletions}[/red]\n"
        f"[bold white]Total TODOs Tracked:[/bold white] {total_todos}",
        title="📊 Session Statistics",
        border_style="cyan"
    ))
    
    # Most active files
    if file_counter:
        console.print("\n[bold cyan]📝 Most Active Files:[/bold cyan]")
        for file, count in file_counter.most_common(5):
            console.print(f"  {count}× [cyan]{file}[/cyan]")
    
    # Most used tags
    if tag_counter:
        console.print("\n[bold magenta]🏷️  Most Used Tags:[/bold magenta]")
        for tag, count in tag_counter.most_common(5):
            console.print(f"  {count}× [magenta]{tag}[/magenta]")
    
    # Daily activity
    if daily_sessions:
        console.print("\n[bold yellow]📅 Most Active Days:[/bold yellow]")
        for date, count in sorted(daily_sessions.items(), key=lambda x: x[1], reverse=True)[:5]:
            console.print(f"  {date}: {count} session(s)")
    
    console.print()

@main.command()
@click.option('--output', '-o', default='brainet_session.md', help='Output markdown file name')
@click.option('--limit', '-n', type=int, help='Number of recent sessions to export (default: 10, use 0 for all)')
@click.option('--today', is_flag=True, help='Export only today\'s sessions')
@click.option('--date', type=str, help='Export sessions from specific date (YYYY-MM-DD)')
def export(output, limit, today, date):
    """Export session history to a markdown file.
    
    Examples:
        brainet export              # Export last 10 sessions
        brainet export -n 5         # Export last 5 sessions
        brainet export -n 0         # Export ALL sessions
        brainet export --today      # Export only today's sessions
        brainet export --date 2025-10-30  # Export sessions from specific date
    """
    context = _ensure_context_capture()
    if not context:
        console.print("[yellow]No active tracking session[/yellow]")
        return
    
    capsule_manager = context.capsule_manager
    capsules = capsule_manager.list_capsules()
    
    if not capsules:
        console.print("[yellow]No sessions to export[/yellow]")
        return
    
    # Filter capsules by date if requested
    import json
    from datetime import datetime, date as date_type
    
    filtered_capsules = []
    
    if today or date:
        # Determine target date
        if today:
            target_date = datetime.now().date()
            filter_desc = "today"
        else:
            try:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                filter_desc = f"from {date}"
            except ValueError:
                console.print(f"[red]Error:[/red] Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-30)")
                return
        
        # Filter capsules by date
        for capsule_path in capsules:
            try:
                with open(capsule_path, 'r') as f:
                    data = json.load(f)
                    timestamp = data.get("metadata", {}).get("timestamp", "")
                    if timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        if dt.date() == target_date:
                            filtered_capsules.append(capsule_path)
            except Exception:
                continue
        
        if not filtered_capsules:
            console.print(f"[yellow]No sessions found {filter_desc}[/yellow]")
            return
        
        capsules_to_export = filtered_capsules
        console.print(f"[cyan]Found {len(capsules_to_export)} session(s) {filter_desc}[/cyan]")
    else:
        # Use limit (default 10, or 0 for all)
        if limit is None:
            limit = 10
        
        if limit == 0:
            capsules_to_export = capsules
        else:
            capsules_to_export = capsules[:limit]
    
    with console.status(f"[yellow]📝 Exporting {len(capsules_to_export)} sessions...[/yellow]"):
        
        md_content = f"# Brainet Session History\n\n"
        md_content += f"**Project:** {context.project_root.name}\n"
        md_content += f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        md_content += f"**Total Sessions:** {len(capsules_to_export)}\n\n"
        md_content += "---\n\n"
        
        for i, capsule_path in enumerate(capsules_to_export, 1):
            try:
                with open(capsule_path, 'r') as f:
                    data = json.load(f)
                
                timestamp = data.get("metadata", {}).get("timestamp", "Unknown")
                context_data = data.get("context", {})
                ai_summary = context_data.get("ai_summary") or "No summary"
                file_diffs = context_data.get("file_diffs", [])
                todos = context_data.get("todos", [])
                commits = context_data.get("recent_commits", [])
                
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime("%B %d, %Y at %H:%M:%S")
                except:
                    time_str = timestamp
                
                md_content += f"## Session {i}\n\n"
                md_content += f"**Date:** {time_str}\n\n"
                md_content += f"**Summary:** {ai_summary}\n\n"
                
                if file_diffs:
                    md_content += f"**Modified Files:** ({len(file_diffs)})\n"
                    for fd in file_diffs[:10]:
                        path = fd.get('file_path', 'Unknown')
                        adds = fd.get('additions', 0)
                        dels = fd.get('deletions', 0)
                        md_content += f"- `{path}` (+{adds} -{dels})\n"
                    md_content += "\n"
                
                if todos:
                    md_content += f"**TODOs:** ({len(todos)})\n"
                    for todo in todos[:5]:
                        file = todo.get('file', 'Unknown')
                        line = todo.get('line', '?')
                        text = todo.get('text', 'No description')
                        md_content += f"- `{file}:{line}` - {text}\n"
                    md_content += "\n"
                
                if commits:
                    md_content += f"**Recent Commits:** ({len(commits)})\n"
                    for commit in commits[:3]:
                        msg = commit.get('message', 'No message')
                        hash_short = commit.get('hash', '')[:7]
                        md_content += f"- `{hash_short}` {msg}\n"
                    md_content += "\n"
                
                md_content += "---\n\n"
                
            except Exception as e:
                md_content += f"## Session {i}\n\n*Error reading session: {e}*\n\n---\n\n"
        
        # Write to file
        output_path = Path(output)
        with open(output_path, 'w') as f:
            f.write(md_content)
    
    console.print(f"[green]✓[/green] Exported {len(capsules_to_export)} sessions to [cyan]{output_path.resolve()}[/cyan]")
    console.print(f"[dim]💡 Open the file to review your development history[/dim]\n")

@main.command()
def status():
    """Show current Brainet tracking status and session information."""
    context_capture = _ensure_context_capture()
    if not context_capture:
        console.print("[yellow]⚠️  No active tracking session[/yellow]")
        console.print("[dim]Run [cyan]brainet start[/cyan] to begin tracking[/dim]")
        return
    
    # Capture current state
    capsule = context_capture.capture_context()
    
    # Build comprehensive status panel
    console.print()
    rprint(Panel.fit(
        f"[bold white]Project:[/bold white] {capsule.project.name}\n"
        f"[bold white]Branch:[/bold white] {capsule.project.git_branch or 'N/A'}\n"
        f"[bold white]Session Started:[/bold white] {context_capture.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[bold white]Tracking Status:[/bold white] [green]● Active[/green]",
        title="📊 Brainet Status",
        border_style="cyan"
    ))
    
    # Show what's being tracked
    modified_count = len(capsule.context.file_diffs)
    todo_count = len(capsule.context.todos)
    commit_count = len(capsule.context.recent_commits)
    
    console.print("\n[bold cyan]📈 Current Activity:[/bold cyan]")
    console.print(f"  [yellow]•[/yellow] {modified_count} file(s) modified")
    console.print(f"  [blue]•[/blue] {todo_count} TODO(s) tracked")
    console.print(f"  [green]•[/green] {commit_count} recent commit(s)")
    
    # Show modified files if any
    if capsule.context.file_diffs:
        console.print("\n[bold yellow]📝 Modified Files:[/bold yellow]")
        for file_diff in capsule.context.file_diffs[:5]:
            changes = f"+{file_diff.additions} -{file_diff.deletions}"
            console.print(f"  • [cyan]{file_diff.file_path}[/cyan] [dim]({changes})[/dim]")
        if len(capsule.context.file_diffs) > 5:
            console.print(f"  [dim]... and {len(capsule.context.file_diffs) - 5} more[/dim]")
    
    # Show active TODOs
    if capsule.context.todos:
        console.print(f"\n[bold blue]📋 Active TODOs:[/bold blue]")
        for todo in capsule.context.todos[:3]:
            console.print(f"  • [dim]{todo.file}:{todo.line}[/dim] - {todo.text}")
        if len(capsule.context.todos) > 3:
            console.print(f"  [dim]... and {len(capsule.context.todos) - 3} more[/dim]")
    
    # Check if there are any capsules saved
    from pathlib import Path
    import json
    brainet_dir = context_capture.project_root / ".brainet"
    capsules_dir = brainet_dir / "capsules"
    if capsules_dir.exists():
        capsule_files = sorted(capsules_dir.glob("capsule_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        capsule_count = len(capsule_files)
        console.print(f"\n[bold green]💾 Storage:[/bold green]")
        console.print(f"  • {capsule_count} capsule(s) saved")
        console.print(f"  • Location: [dim]{capsules_dir}[/dim]")
        
        # Show last saved work summary
        if capsule_files:
            try:
                with open(capsule_files[0], 'r') as f:
                    last_capsule = json.load(f)
                    ai_summary = last_capsule.get('context', {}).get('ai_summary', '')
                    timestamp = last_capsule.get('metadata', {}).get('timestamp', '')
                    
                    if ai_summary:
                        console.print(f"\n[bold magenta]🕐 Last Saved Work:[/bold magenta]")
                        console.print(f"  [dim]{timestamp}[/dim]")
                        console.print(f"  {ai_summary}")
            except Exception:
                pass  # Skip if can't read last capsule
    
    console.print(f"\n[dim]💡 Use [cyan]brainet capture[/cyan] to save current state[/dim]")
    console.print(f"[dim]💡 Use [cyan]brainet pause[/cyan] to stop tracking[/dim]\n")

@main.command()
def preview():
    """Preview what would be captured without saving."""
    context_capture = _ensure_context_capture()
    if not context_capture:
        console.print("[yellow]⚠️  No active tracking session[/yellow]")
        console.print("[dim]Run [cyan]brainet start[/cyan] to begin tracking[/dim]")
        return
    
    with console.status("[yellow]📋 Analyzing current state...[/yellow]"):
        capsule = context_capture.capture_context()
    
    # Show what would be captured
    modified_count = len(capsule.context.file_diffs)
    todo_count = len(capsule.context.todos)
    commit_count = len(capsule.context.recent_commits)
    
    console.print()
    rprint(Panel.fit(
        f"[bold cyan]Preview - What Would Be Captured:[/bold cyan]\n\n"
        f"[bold white]Modified Files:[/bold white] {modified_count}\n"
        f"[bold white]TODOs:[/bold white] {todo_count}\n"
        f"[bold white]Recent Commits:[/bold white] {commit_count}",
        title="🔍 Preview",
        border_style="yellow"
    ))
    
    # Show file details
    if capsule.context.file_diffs:
        console.print("\n[bold cyan]📝 Files That Would Be Saved:[/bold cyan]")
        for fd in capsule.context.file_diffs[:10]:  # Limit to 10
            additions = fd.additions
            deletions = fd.deletions
            console.print(f"  • {fd.file_path} [green]+{additions}[/green] [red]-{deletions}[/red]")
    
    # Show TODOs
    if capsule.context.todos:
        console.print("\n[bold cyan]📋 TODOs That Would Be Saved:[/bold cyan]")
        for todo in capsule.context.todos[:5]:  # Limit to 5
            console.print(f"  • {todo.file}:{todo.line} - {todo.text}")
    
    # Generate AI summary preview
    if modified_count > 0 or commit_count > 0:
        with console.status("[yellow]🤖 Generating AI summary preview...[/yellow]"):
            from .ai.session_summarizer import SessionSummarizerSync
            summarizer = SessionSummarizerSync(use_ai=True)
            
            capsule_data = {
                "git_info": {
                    "current_branch": capsule.project.git_branch or "unknown",
                    "uncommitted_changes": len(capsule.context.file_diffs) > 0
                },
                "file_changes": [
                    {
                        "path": f.file_path,
                        "additions": f.additions,
                        "deletions": f.deletions,
                        "diff": f.diff
                    }
                    for f in capsule.context.file_diffs
                ],
                "recent_commits": [
                    {
                        "hash": c.hash if hasattr(c, 'hash') else c.get("hash", ""),
                        "message": c.message if hasattr(c, 'message') else c.get("message", ""),
                        "timestamp": c.timestamp.isoformat() if hasattr(c, 'timestamp') else c.get("timestamp", "")
                    }
                    for c in capsule.context.recent_commits
                ],
                "todos": [
                    {"file": t.file, "line": t.line, "text": t.text}
                    for t in capsule.context.todos
                ]
            }
            
            summary = summarizer.generate_summary(capsule_data)
            
            console.print(f"\n[bold magenta]🤖 AI Summary Preview:[/bold magenta]")
            console.print(f"  {summary}")
    
    console.print(f"\n[dim]💡 Run [cyan]brainet capture[/cyan] to save this snapshot[/dim]")
    console.print(f"[dim]💡 Run [cyan]brainet status[/cyan] for current session info[/dim]\n")

@main.command()
@click.argument('query', nargs=-1)
def ask(query):
    """Ask a natural language question about your development context."""
    asyncio.run(_ask_async(query))

async def _ask_async(query):
    context = _ensure_context_capture()
    if not context:
        console.print("[yellow]No active tracking session[/yellow]")
        return

    capsule = context.capture_context()
    query_text = " ".join(query)
    
    file_contents = {}
    import re
    file_mentions = re.findall(r'[\w/.-]+\.\w+', query_text)
    
    if file_mentions:
        project_root = context.project_root
        for filename in file_mentions:
            # Try to find the file
            file_path = project_root / filename
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    # Limit content size
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    file_contents[filename] = content
                except Exception:
                    pass
    
    # Build structured context for AI comprehension
    context_text = (
        f"Project: {capsule.project.name}\n"
        f"Branch: {capsule.project.git_branch}\n\n"
        "Modified Files:\n"
        + "\n".join(f"• {f.path}" for f in capsule.context.modified_files)
        + "\n\nTODOs:\n"
        + "\n".join(f"• {todo.file}: {todo.text}" for todo in capsule.context.todos)
        + "\n\nRecent Commits:\n"
        + "\n".join(f"• {c.message}" for c in capsule.context.recent_commits)
    )

    from .ai.session_summarizer import SessionSummarizer
    summarizer = SessionSummarizer(use_ai=True)
    
    # Transform capsule to dict format with full diff context
    capsule_data = {
        "git_info": {
            "current_branch": capsule.project.git_branch or "unknown",
        },
        "file_changes": [
            {
                "path": f.file_path,
                "change_type": f.change_type,
                "diff": f.diff
            }
            for f in capsule.context.file_diffs
        ],
        "todos": [
            {"file": t.file, "line": t.line, "text": t.text}
            for t in capsule.context.todos
        ],
        "recent_commits": [
            {"message": c.message, "hash": c.hash}
            for c in capsule.context.recent_commits[:5]
        ],
        "file_contents": file_contents  # Add file contents if mentioned
    }
    
    with console.status("[bold cyan]Thinking...[/bold cyan]"):
        try:
            answer = await summarizer.explain_why(capsule_data, query_text)
            console.print("\n[bold green]Answer:[/bold green]")
            console.print(answer.strip())
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            console.print("[red]Sorry, I couldn't generate an answer.[/red]")


def _find_all_projects():
    """Helper to find all brainet projects, deduplicated."""
    import os
    
    # Search common project locations
    search_paths = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Projects",
    ]
    
    projects = {}  # Use dict to deduplicate by path
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        
        # Find all .brainet directories
        for root, dirs, files in os.walk(search_path):
            if '.brainet' in dirs:
                brainet_dir = Path(root) / '.brainet'
                session_file = brainet_dir / '_session.json'
                
                if session_file.exists():
                    try:
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)
                            project_root = Path(session_data['project_root'])
                            
                            # Get last capsule time
                            capsule_dir = brainet_dir / 'capsules'
                            last_activity = None
                            capsule_count = 0
                            
                            if capsule_dir.exists():
                                capsules = list(capsule_dir.glob('*.json'))
                                capsule_count = len(capsules)
                                if capsules:
                                    latest_capsule = max(capsules, key=lambda p: p.stat().st_mtime)
                                    last_activity = datetime.fromtimestamp(latest_capsule.stat().st_mtime)
                            
                            # Use path as key to deduplicate
                            projects[str(project_root)] = {
                                'project': project_root.name,
                                'path': str(project_root),
                                'capsules': capsule_count,
                                'last_activity': last_activity
                            }
                    except Exception:
                        pass
                
                # Don't recurse into .brainet directories
                dirs.remove('.brainet')
    
    return list(projects.values())


@main.command()
def workspaces():
    """List all active brainet sessions across all projects."""
    sessions = _find_all_projects()
    
    if not sessions:
        console.print("[yellow]No active brainet sessions found.[/yellow]")
        console.print("\n[dim]💡 Run [cyan]brainet start[/cyan] in a project to begin tracking[/dim]")
        return
    
    # Sort by last activity
    sessions.sort(key=lambda s: s['last_activity'] or datetime.min, reverse=True)
    
    console.print(f"\n[bold cyan]📚 Active Brainet Sessions ({len(sessions)}):[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan", width=20)
    table.add_column("Location", style="dim", width=40)
    table.add_column("Capsules", justify="right", style="green")
    table.add_column("Last Activity", style="yellow")
    
    for session in sessions:
        last_activity_str = "Never"
        if session['last_activity']:
            delta = datetime.now() - session['last_activity']
            if delta < timedelta(hours=1):
                last_activity_str = f"{int(delta.total_seconds() / 60)} min ago"
            elif delta < timedelta(days=1):
                last_activity_str = f"{int(delta.total_seconds() / 3600)} hours ago"
            else:
                last_activity_str = f"{delta.days} days ago"
        
        # Truncate path if too long
        path_display = session['path']
        if len(path_display) > 40:
            path_display = "..." + path_display[-37:]
        
        table.add_row(
            session['project'],
            path_display,
            str(session['capsules']),
            last_activity_str
        )
    
    console.print(table)
    console.print(f"\n[dim]💡 Use [cyan]cd <path>[/cyan] and [cyan]brainet resume[/cyan] to continue a session[/dim]\n")


@main.command()
@click.argument('query', nargs=-1, required=True)
@click.option('--all-projects', '-a', is_flag=True, help='Search across all projects')
def search(query, all_projects):
    """Search for sessions by content across projects."""
    query_text = " ".join(query).lower()
    
    if all_projects:
        # Search all projects using helper
        projects = _find_all_projects()
        results = []
        
        for project in projects:
            brainet_dir = Path(project['path']) / '.brainet'
            capsule_dir = brainet_dir / 'capsules'
            
            if capsule_dir.exists():
                for capsule_file in capsule_dir.glob('*.json'):
                    try:
                        with open(capsule_file, 'r') as f:
                            capsule_data = json.load(f)
                            
                            # Search in summary, files, commits
                            summary = capsule_data.get('context', {}).get('ai_summary', '').lower()
                            files = str(capsule_data.get('context', {}).get('file_diffs', [])).lower()
                            commits = str(capsule_data.get('context', {}).get('recent_commits', [])).lower()
                            
                            if query_text in summary or query_text in files or query_text in commits:
                                results.append({
                                    'project': project['project'],
                                    'timestamp': capsule_data.get('metadata', {}).get('timestamp', ''),
                                    'summary': capsule_data.get('context', {}).get('ai_summary', 'No summary'),
                                    'path': project['path']
                                })
                    except Exception:
                        pass
        
        if not results:
            console.print(f"\n[yellow]No results found for:[/yellow] [cyan]{query_text}[/cyan]")
            return
        
        console.print(f"\n[bold cyan]🔍 Search Results for '{query_text}' ({len(results)} found):[/bold cyan]\n")
        
        for result in results[:20]:  # Limit to 20 results
            console.print(f"[bold green]●[/bold green] [cyan]{result['project']}[/cyan] [dim]({result['timestamp']})[/dim]")
            console.print(f"  {result['summary'][:100]}...")
            console.print(f"  [dim]{result['path']}[/dim]\n")
        
        if len(results) > 20:
            console.print(f"[dim]... and {len(results) - 20} more results[/dim]\n")
    
    else:
        # Search current project only
        project_root = _find_project_root()
        capsule_dir = project_root / ".brainet" / "capsules"
        
        if not capsule_dir.exists():
            console.print("[yellow]No capsules found in current project.[/yellow]")
            return
        
        results = []
        for capsule_file in capsule_dir.glob('*.json'):
            try:
                with open(capsule_file, 'r') as f:
                    capsule_data = json.load(f)
                    
                    summary = capsule_data.get('context', {}).get('ai_summary', '').lower()
                    files = str(capsule_data.get('context', {}).get('file_diffs', [])).lower()
                    
                    if query_text in summary or query_text in files:
                        results.append({
                            'timestamp': capsule_data.get('metadata', {}).get('timestamp', ''),
                            'summary': capsule_data.get('context', {}).get('ai_summary', 'No summary'),
                            'files': len(capsule_data.get('context', {}).get('file_diffs', []))
                        })
            except Exception:
                pass
        
        if not results:
            console.print(f"\n[yellow]No results found for:[/yellow] [cyan]{query_text}[/cyan]")
            console.print("[dim]💡 Use --all-projects to search across all projects[/dim]")
            return
        
        console.print(f"\n[bold cyan]🔍 Found {len(results)} sessions matching '{query_text}':[/bold cyan]\n")
        
        for result in results:
            console.print(f"[bold green]●[/bold green] [dim]{result['timestamp']}[/dim] - {result['files']} files")
            console.print(f"  {result['summary']}\n")


@main.command()
def switch():
    """View all brainet projects for quick navigation.
    
    Shows all active brainet sessions sorted by recent activity.
    Copy the path and use 'cd <path>' to switch projects.
    """
    sessions = _find_all_projects()
    
    if not sessions:
        console.print("[yellow]No active brainet sessions found.[/yellow]")
        console.print("\n[dim]💡 Run [cyan]brainet start[/cyan] in a project to begin tracking[/dim]")
        return
    
    # Sort by last activity
    sessions.sort(key=lambda s: s['last_activity'] or datetime.min, reverse=True)
    
    console.print("\n[bold cyan]🔀 Available Projects:[/bold cyan]\n")
    
    for i, session in enumerate(sessions, 1):
        last_activity_str = "Never"
        if session['last_activity']:
            delta = datetime.now() - session['last_activity']
            if delta < timedelta(hours=1):
                last_activity_str = f"{int(delta.total_seconds() / 60)} min ago"
            elif delta < timedelta(days=1):
                last_activity_str = f"{int(delta.total_seconds() / 3600)} hours ago"
            else:
                last_activity_str = f"{delta.days} days ago"
        
        console.print(f"  [cyan]{i}.[/cyan] [bold]{session['project']}[/bold] [dim]({last_activity_str})[/dim]")
        console.print(f"     [green]cd {session['path']}[/green]\n")
    
    console.print("[dim]💡 Copy a path above and run: [green]cd <path>[/green][/dim]")
    console.print("[dim]💡 Then run: [cyan]brainet resume[/cyan] to continue your session[/dim]\n")


@main.command()
@click.option('--days', default=30, help='Remove sessions older than N days')
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned without deleting')
def cleanup(days, dry_run):
    """Clean up old brainet sessions across all projects."""
    from datetime import timedelta
    
    cutoff_date = datetime.now() - timedelta(days=days)
    projects = _find_all_projects()
    
    projects_to_clean = []
    total_capsules = 0
    
    for project in projects:
        brainet_dir = Path(project['path']) / '.brainet'
        capsule_dir = brainet_dir / 'capsules'
        
        if capsule_dir.exists():
            old_capsules = []
            for capsule_file in capsule_dir.glob('*.json'):
                mtime = datetime.fromtimestamp(capsule_file.stat().st_mtime)
                if mtime < cutoff_date:
                    old_capsules.append(capsule_file)
            
            if old_capsules:
                projects_to_clean.append({
                    'project': project['project'],
                    'path': project['path'],
                    'capsules': old_capsules
                })
                total_capsules += len(old_capsules)
    
    if not projects_to_clean:
        console.print(f"\n[green]✓[/green] No capsules older than {days} days found.")
        return
    
    if dry_run:
        console.print(f"\n[yellow]🔍 Dry Run - Would remove {total_capsules} capsules from {len(projects_to_clean)} projects:[/yellow]\n")
        for proj in projects_to_clean:
            console.print(f"  [cyan]●[/cyan] {proj['project']}: {len(proj['capsules'])} capsules")
        console.print(f"\n[dim]Run without --dry-run to actually delete[/dim]\n")
    else:
        console.print(f"\n[yellow]🗑️  Removing {total_capsules} old capsules from {len(projects_to_clean)} projects...[/yellow]\n")
        
        for proj in projects_to_clean:
            for capsule in proj['capsules']:
                capsule.unlink()
            console.print(f"  [green]✓[/green] Cleaned {proj['project']}: {len(proj['capsules'])} capsules removed")
        
        console.print(f"\n[green]✓[/green] Cleanup complete!\n")


if __name__ == "__main__":
    main()