"""Configuration settings for Brainet."""

import os

# AI Provider Selection
AI_PROVIDER = os.getenv("BRAINET_AI_PROVIDER", "groq")  # "groq" or "ollama"

# Groq API settings (FAST & FREE cloud API - recommended!)
GROQ_CONFIG = {
    "api_key": os.getenv("GROQ_API_KEY", ""),  # Set via environment variable
    "model": "llama-3.3-70b-versatile",  # FREE tier, 500+ tokens/sec
    "temperature": 0.3
}

# Ollama API settings (Local inference - fallback)
OLLAMA_CONFIG = {
    "model": "llama3.2:1b",  # Fast, small model - good for local inference
    "temperature": 0.3,
    "context_window": 2048
}

# File monitoring settings
WATCH_PATTERNS = ["*.py", "*.js", "*.ts", "*.json"]
IGNORE_PATTERNS = ["*/.git/*", "*/__pycache__/*", "*/node_modules/*", "*/.brainet/*"]

# Performance settings
MAX_FILES_TO_ANALYZE = 50  # Limit file diff analysis for speed
MAX_DIFF_SIZE = 10000  # Max characters per diff

# Context analysis settings
CONTEXT_WINDOW = 8000  # Max characters for context analysis
MIN_MEANINGFUL_CHANGE = 10  # Minimum characters changed to consider "meaningful"

# Session settings
MAX_SESSION_AGE_HOURS = 8  # Auto-detect new session after this many hours
