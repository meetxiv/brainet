# 🧠 Brainet

**Never lose your train of thought again.**

Brainet is an AI-powered development context tracker that automatically captures what you're working on, why you're working on it, and what's next. Think of it as a second brain for your coding sessions.

<p align="center">
<a href="https://pypi.org/project/brainet/">
  <img src="https://img.shields.io/pypi/v/brainet" alt="PyPI version">
</a>
  <img src="https://img.shields.io/pypi/pyversions/brainet" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

---

## 🚀 What's New in v0.2.0

**Major Architecture Overhaul - 5-Source Intelligence System:**

- **🔍 SOURCE 1 - Git Diffs**: Smart chunking with AST-based function extraction
- **📄 SOURCE 2 - Full Files**: Complete code context for accurate answers
- **🌲 SOURCE 3 - AST Analysis**: Deep code structure understanding (classes, methods, imports)
- **🎯 SOURCE 4 - Semantic Search**: Proactive code discovery related to your queries
- **📦 SOURCE 5 - Project Metadata**: Dependencies, file types, and project structure

**Critical Bugs Fixed:**
- ✅ Ask command now provides specific, detailed answers with line numbers
- ✅ Proper diff counting (additions/deletions) in all scenarios

**New Features:**
- 🎨 Capsule indexing (#01, #02, #03 format)
- 👁️ `brainet preview <index>` - View any historical capsule
- 💬 Dramatically improved AI responses - specific method listings, accurate context


---

## 🤔 The Problem

You're deep in the zone, building a feature. Then...
- 📧 An urgent email arrives
- 🔥 A production bug needs fixing  
- ☕ You take a break
- 📅 It's Friday, you'll continue Monday

**Monday morning:** *"Wait... what was I doing? Why did I change this file? What was the plan?"*

You spend 30 minutes scrolling through git commits, reading code, trying to remember. Your flow state? Gone.

## ✨ The Solution

Brainet captures your coding sessions automatically and uses AI to create human-readable summaries:

```bash
$ brainet capture

📸 Context Captured
────────────────────────────────────────────────────────────────
Added a Character class with methods for combat (attack, 
take_damage, heal), progression (gain_experience, level_up), 
and status checking (is_alive). Also added Inventory class 
with item management.

📊 Stats:
   • 1 files modified
   • 67 lines added
   • 3 TODOs found

✓ Capsule saved: 2025-11-02 15:45:53
────────────────────────────────────────────────────────────────
```

Now when you come back, just run `brainet history` and instantly remember everything.

---

## 🚀 Quick Start

### Installation

```bash
# 1. Install brainet
pip install brainet --user

# 2. Add to PATH permanently
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Setup

```bash
# 1. Check it works
brainet --version

# 2. Get free API key from https://console.groq.com/keys

# 3. Set it permanently
echo 'export GROQ_API_KEY="gsk_your_key_here"' >> ~/.zshrc
source ~/.zshrc

# 4. Start using brainet in any git project!
cd your-project

brainet start
# ... make some changes ...
brainet capture --tag feature -m "Added user authentication"
```

That's it! Brainet is now tracking your development context.

---

## 💡 Key Features

### 🤖 AI-Powered Summaries
Brainet uses Claude Sonnet 3.5 (via Groq) to understand your changes and generate intelligent summaries. It knows the difference between:
- Major features vs minor refactors
- Bug fixes vs new functionality  
- Breaking changes vs safe updates

### 🔍 Natural Language Querying (Powered by 5 Sources)
Ask questions about your work in plain English - now with comprehensive context:

```bash
$ brainet ask "what methods does the Character class have?"

You have a Character class with these methods: __init__ 
(lines 4-10), take_damage (lines 12-15), heal (lines 17-20), 
is_alive (lines 22-23), attack (lines 25-27), gain_experience 
(lines 29-32), and level_up (lines 34-39). The TODOs include 
adding a magic system with spells, implementing quest tracking, 
and adding save/load game functionality.
```

**v0.2.0 Intelligence:** Brainet now searches through full file contents, AST structure, and semantically related code to give you accurate, detailed answers with line numbers.

### 🏢 Multi-Project Support
Working on multiple projects? Brainet handles it seamlessly:

```bash
$ brainet workspaces

📚 Active Brainet Sessions (3):
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Project      ┃ Location               ┃ Capsules ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ api-backend  │ ~/projects/api         │       12 │
│ frontend-app │ ~/projects/frontend    │        8 │
│ mobile-app   │ ~/projects/mobile      │        5 │
└──────────────┴────────────────────────┴──────────┘
```

> **📍 Note:** The `workspaces` command scans these directories for brainet projects:
> - `~/Desktop` - For desktop projects
> - `~/Documents` - For document-based work
> - `~/Projects` - For dedicated project folders
> 
> Keep your projects in these locations for automatic discovery!

### 🔎 Cross-Project Search
Find where you implemented that feature across all your projects:

```bash
$ brainet search "authentication" --all-projects

🔍 Found in 3 projects:
  • api-backend: JWT authentication with refresh tokens
  • frontend-app: Google OAuth integration
  • mobile-app: Biometric authentication added
```

### 📊 Development Analytics
Understand your coding patterns:

```bash
$ brainet stats

📊 Development Insights
────────────────────────────────────────
  Sessions: 47
  Files modified: 234
  Most active file: auth.py (23 changes)
  Top tags: feature, bugfix, refactor
  
  Recent activity:
  • 15 sessions this week
  • Peak productivity: Tuesday afternoons
────────────────────────────────────────
```

---

## 📚 Commands

| Command | Description |
|---------|-------------|
| `brainet start` | Initialize tracking in current project |
| `brainet capture` | Save current session with AI summary |
| `brainet history` | View all captured sessions with #01, #02 indexing |
| `brainet preview` | Preview what will be captured next |
| `brainet preview <N>` | View historical capsule #N |
| `brainet ask "question"` | Query your work with AI (v0.2.0: 5-source intelligence) |
| `brainet search "keyword"` | Search across sessions |
| `brainet workspaces` | List all tracked projects |
| `brainet stats` | View development analytics |
| `brainet export` | Export sessions to Markdown |
| `brainet diff <file>` | View colorized file changes |
| `brainet switch` | Quick navigation between projects |

Run `brainet --help` for full command list.

---

## 🎯 Real-World Use Cases

### 1. **Context Switching**
Switch between tasks without losing context:
```bash
# Working on Feature A
brainet capture --tag feature-a

# Emergency bug fix needed
brainet pause
cd ~/other-project
brainet start
# Fix bug...
brainet capture --tag hotfix

# Back to Feature A
cd ~/original-project
brainet resume  # Instantly recall where you left off
```

### 2. **Code Reviews**
Generate PR descriptions automatically:
```bash
brainet export --since yesterday

# Copy the AI-generated summary into your PR
```

### 3. **Weekly Standups**
"What did I work on this week?"
```bash
brainet history --since "1 week ago"

# See all your accomplishments summarized
```

### 4. **Knowledge Transfer**
Onboarding a teammate:
```bash
brainet export --tag authentication > auth_work.md

# Share the complete history of authentication feature
```

---

## 🛠️ How It Works

1. **File Watching** - Tracks changes in your git repository
2. **Git Integration** - Captures commits, diffs, and file changes
3. **TODO Extraction** - Finds TODO comments automatically
4. **AI Analysis** - Claude Sonnet 3.5 generates intelligent summaries
5. **Local Storage** - Everything saved locally in `.brainet/` folder

**Privacy First:** All your data stays on your machine. AI summaries are generated via API but your code never leaves your control.

---

## 🔧 Configuration

### API Keys

Brainet supports two AI providers:

**Groq (Recommended)** - Free, fast, 500+ tokens/sec
```bash
export GROQ_API_KEY="your_key_here"
```

**Anthropic Claude** - More powerful, requires paid account
```bash
export ANTHROPIC_API_KEY="your_key_here"
```

### Advanced Options

```bash
# Capture with custom tags
brainet capture --tag feature --tag auth -m "Added JWT support"

# Export filtered sessions
brainet export --tag bugfix --since "2024-10-01"

# Search in current project only
brainet search "payment integration"

# Clean up old sessions
brainet cleanup --days 90
```

---

## 🎓 Best Practices

1. **Capture Often** - At least once per coding session
2. **Use Tags** - Organize with `--tag feature`, `--tag bugfix`, etc.
3. **Add Messages** - Use `-m` for important context
4. **Regular Cleanup** - Run `brainet cleanup` monthly
5. **Export Important Work** - Save milestones to Markdown
6. **Organize Projects** - Keep projects in `~/Desktop`, `~/Documents`, or `~/Projects` for the `workspaces` command to find them automatically

---

## 🤝 Contributing

Brainet is open source! Contributions welcome:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [Anthropic Claude](https://anthropic.com)
- Powered by [Groq](https://groq.com) for fast AI inference
- Uses [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- Created for developers, by developers

---

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/meetjoshi/brainet/issues)
- **Discussions:** [GitHub Discussions](https://github.com/meetjoshi/brainet/discussions)
- **Email:** meetxiv@gmail.com

---

<p align="center">
  <strong>Stop losing context. Start using Brainet.</strong>
  <br><br>
  Made with ❤️ for developers who value flow state
</p>
