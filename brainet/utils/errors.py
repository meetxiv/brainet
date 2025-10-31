"""Error handling utilities for Brainet."""

from rich.console import Console

console = Console()


class BrainetError(Exception):
    """Base exception for Brainet errors."""
    pass


class NotInGitRepoError(BrainetError):
    """Raised when operation requires a git repository."""
    pass


class NoActiveSessionError(BrainetError):
    """Raised when no brainet session is active."""
    pass


class APIKeyMissingError(BrainetError):
    """Raised when AI API key is not configured."""
    pass


class NetworkError(BrainetError):
    """Raised when network request fails."""
    pass


def handle_error(error: Exception, command: str = None):
    """Display user-friendly error messages."""
    
    if isinstance(error, NotInGitRepoError):
        console.print("\n[red]❌ Error:[/red] Not a git repository\n")
        console.print("[yellow]💡 Quick fix:[/yellow]")
        console.print("   git init")
        console.print("   brainet start\n")
        console.print("[dim]📚 Brainet works best with git-tracked projects[/dim]\n")
        
    elif isinstance(error, NoActiveSessionError):
        console.print("\n[red]❌ Error:[/red] No active brainet session\n")
        console.print("[yellow]💡 Quick fix:[/yellow]")
        console.print("   brainet start\n")
        console.print("[dim]📚 Run 'brainet --help' to see all commands[/dim]\n")
        
    elif isinstance(error, APIKeyMissingError):
        console.print("\n[red]❌ Error:[/red] AI API key not configured\n")
        console.print("[yellow]💡 Setup instructions:[/yellow]")
        console.print("   export GROQ_API_KEY='your_key_here'")
        console.print("   # Get free API key at: https://console.groq.com/keys\n")
        console.print("[dim]Or add to ~/.bashrc or ~/.zshrc for persistence[/dim]\n")
        
    elif isinstance(error, NetworkError):
        console.print("\n[red]❌ Error:[/red] Network request failed\n")
        console.print("[yellow]💡 Troubleshooting:[/yellow]")
        console.print("   • Check your internet connection")
        console.print("   • Verify API key is correct")
        console.print("   • Try again in a moment\n")
        
    elif isinstance(error, FileNotFoundError):
        console.print(f"\n[red]❌ Error:[/red] File not found: {error}\n")
        console.print("[yellow]💡 Tip:[/yellow]")
        console.print("   Make sure you're in the correct directory\n")
        
    elif isinstance(error, PermissionError):
        console.print(f"\n[red]❌ Error:[/red] Permission denied: {error}\n")
        console.print("[yellow]💡 Tip:[/yellow]")
        console.print("   Check file permissions or run with appropriate access\n")
        
    elif isinstance(error, KeyboardInterrupt):
        console.print("\n\n[yellow]Cancelled by user[/yellow]")
        
    else:
        # Generic error with helpful context
        console.print(f"\n[red]❌ Unexpected error:[/red] {type(error).__name__}")
        console.print(f"   {str(error)}\n")
        
        if command:
            console.print(f"[dim]While running: brainet {command}[/dim]")
        
        console.print("\n[yellow]💡 Need help?[/yellow]")
        console.print("   • Run 'brainet --help'")
        console.print("   • Check the docs: github.com/yourusername/brainet")
        console.print("   • Report issue: github.com/yourusername/brainet/issues\n")


def safe_execute(func, error_context: str = None):
    """Wrapper for safe command execution with error handling."""
    try:
        return func()
    except (BrainetError, FileNotFoundError, PermissionError, KeyboardInterrupt) as e:
        handle_error(e, error_context)
        raise SystemExit(1)
    except Exception as e:
        handle_error(e, error_context)
        raise SystemExit(1)
