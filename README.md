# 🧠 Brainet

**Never lose your train of thought again.**

Brainet is an AI-powered development context tracker that automatically captures what you're working on, why you're working on it, and what's next. Think of it as a second brain for your coding sessions.

<p align="center">
  <img src="https://img.shields.io/pypi/v/brainet" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/brainet" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

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
Implemented VIP tier system with 5 levels (Bronze to Diamond), 
automatic tier upgrades based on wagering, and bonus multipliers 
from 1.0x to 1.25x. Added daily deposit and loss limits for 
responsible gambling features.

📊 Stats:
   • 3 files modified
   • 147 lines added
   • 5 TODOs found

✓ Capsule saved: 2025-10-31 16:45:23
────────────────────────────────────────────────────────────────
```

Now when you come back, just run `brainet history` and instantly remember everything.

---

## 🚀 Quick Start

### Installation

```bash
pip install brainet
```

### Setup

```bash
# 1. Get a free API key from Groq (takes 30 seconds)
#    https://console.groq.com/keys

# 2. Set your API key
export GROQ_API_KEY="your_key_here"

# 3. Start tracking in your project
cd your-project/
brainet start

# 4. Work on your code...
# (make changes, commit, etc.)

# 5. Capture your session
brainet capture
```

That's it! Brainet is now tracking your development context.

---

## 💡 Key Features

### 🤖 AI-Powered Summaries
Brainet uses Claude Sonnet 3.5 (via Groq) to understand your changes and generate intelligent summaries. It knows the difference between:
- Major features vs minor refactors
- Bug fixes vs new functionality  
- Breaking changes vs safe updates

### 🔍 Natural Language Querying
Ask questions about your work in plain English:

```bash
$ brainet ask "what VIP tiers did I create?"

You created 5 VIP tiers: Bronze, Silver, Gold, Platinum, and 
Diamond. Each tier has different bonus multipliers ranging from 
1.0x to 1.25x based on wagering volume...
```

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
| `brainet history` | View all captured sessions |
| `brainet ask "question"` | Query your work with AI |
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
- **Email:** meet@brainet.dev

---

<p align="center">
  <strong>Stop losing context. Start using Brainet.</strong>
  <br><br>
  Made with ❤️ for developers who value flow state
</p>
