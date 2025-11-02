"""Transforms raw development context into human-readable summaries using Llama 3.3 70B via Groq."""

from typing import List, Dict
from pathlib import Path
import re
import asyncio


class SessionSummarizer:
    
    def __init__(self, use_ai: bool = True):
        self.use_ai = use_ai
        self.ai_available = False
        self.ai_client = None
        
        if use_ai:
            try:
                from ..core.config import GROQ_CONFIG
                from .groq_client import GroqClient
                
                api_key = GROQ_CONFIG.get("api_key")
                if not api_key:
                    raise ValueError("GROQ_API_KEY not set in environment")
                self.ai_client = GroqClient(api_key=api_key, model=GROQ_CONFIG["model"])
                self.ai_available = True
                    
            except Exception as e:
                print(f"[Brainet] ⚠ AI unavailable: {e}")
                print("[Brainet] → Using rule-based fallback")
                self.use_ai = False
    
    async def generate_summary(self, capsule_data: Dict) -> str:
        if self.ai_available and self.ai_client:
            try:
                return await self._generate_ai_summary(capsule_data)
            except Exception as e:
                print(f"[Brainet] AI failed: {e}, using fallback")
        
        return self._generate_rule_based_summary(capsule_data)
    
    async def _generate_ai_summary(self, capsule_data: Dict) -> str:
        context = self._build_context(capsule_data)
        
        files = capsule_data.get("file_changes", [])
        
        if not files:
            return "No code changes detected. Session captured for tracking."
        
        # Prompt engineering: Focus AI on CURRENT session only, no historical context
        prompt = f"""Summarize the changes in ONE concise sentence.

CRITICAL: Only describe changes shown in the "Code changes:" section below. 
DO NOT reference commit history, previous work, or anything not in the diffs.

{context}

Read the changes:
- "Code changes:" = actual code modifications (REMOVED/ADDED lines)
- "Comment/TODO changes:" = comments and TODOs (NOT code!)

Rules:
- ONE sentence maximum (or two very short sentences)
- Be specific about what code changed in THIS session only
- Don't confuse comments with code
- Mention function names if functions were added/removed
- State facts only, no fluff
- NEVER mention "refactored", "previously added", or historical work

Examples:
- "Changed print statement from 'Hello Brainet' to 'Hellloo Brainnnet2.0' and added TODO."
- "Added lcm function to math_utils.py."
- "Modified database connection string."
- "Added calculate_vip_cashback() method with tier-based cashback rates."

Your turn - ONE sentence describing ONLY the current session changes:"""

        response = await self.ai_client.generate(prompt=prompt, max_tokens=200)
        summary = response.strip()
        
        if len(summary) < 10:
            raise ValueError("AI response too short")
        
        return summary
    
    def _build_context(self, capsule_data: Dict) -> str:
        parts = []
        
        git = capsule_data.get("git_info", {})
        files = capsule_data.get("file_changes", [])
        # REMOVED: commits = capsule_data.get("recent_commits", [])  # Ignore commit history
        todos = capsule_data.get("todos", [])
        
        # Noise filter: exclude non-code files
        DATA_FILE_EXTENSIONS = {'.json', '.db', '.sqlite', '.xml', '.yml', '.yaml', '.DS_Store', '.pyc'}
        DATA_PATTERNS = ['capsule_', '.brainet/', '__pycache__/', '.egg-info/']
        
        code_files = []
        data_files = []
        
        for f in files:
            file_path = f.get('path', '')
            is_data_file = (
                any(file_path.endswith(ext) for ext in DATA_FILE_EXTENSIONS) or
                any(pattern in file_path for pattern in DATA_PATTERNS)
            )
            
            if is_data_file:
                data_files.append(f)
            else:
                code_files.append(f)
        
        # Prioritize code files for analysis, fall back to all if no code changes
        files_to_analyze = code_files if code_files else files
        
        if git:
            parts.append(f"Branch: {git.get('current_branch', 'unknown')}")
        
        # REMOVED: Recent commits section - we only care about current session diffs
        # if commits:
        #     parts.append(f"\nRecent commits ({len(commits)}):")
        #     for commit in commits[:3]:
        #         parts.append(f"  • {commit.get('hash', 'unknown')}: {commit.get('message', 'No message')}")
        
        if files_to_analyze:
            parts.append(f"\nModified files:")
            for f in files_to_analyze[:5]:
                file_path = f.get('path')
                parts.append(f"\n📄 {file_path}")
                
                # Show actual diff content for AI analysis
                diff = f.get('diff', '')
                if diff:
                    added_lines = []
                    removed_lines = []
                    added_comments = []
                    removed_comments = []
                    
                    for line in diff.split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            clean = line[1:].strip()
                            if len(clean) > 0:
                                # Separate comments from code
                                if clean.startswith('#'):
                                    added_comments.append(clean)
                                else:
                                    added_lines.append(clean)
                        elif line.startswith('-') and not line.startswith('---'):
                            clean = line[1:].strip()
                            if len(clean) > 0:
                                # Separate comments from code
                                if clean.startswith('#'):
                                    removed_comments.append(clean)
                                else:
                                    removed_lines.append(clean)
                    
                    # Detect function changes
                    added_funcs = {line.split('(')[0] for line in added_lines if line.startswith('def ')}
                    removed_funcs = {line.split('(')[0] for line in removed_lines if line.startswith('def ')}
                    
                    truly_removed = removed_funcs - added_funcs
                    truly_added = added_funcs - removed_funcs
                    
                    # Show function changes if any
                    if truly_added:
                        parts.append(f"   New functions: {', '.join(f.replace('def ', '') for f in truly_added)}")
                    
                    if truly_removed:
                        parts.append(f"   Removed functions: {', '.join(f.replace('def ', '') for f in truly_removed)}")
                    
                    # Show actual code changes (not comments)
                    if added_lines or removed_lines:
                        parts.append(f"   Code changes:")
                        # Show removed code
                        for line in removed_lines[:5]:
                            parts.append(f"     REMOVED: {line}")
                        # Show added code
                        for line in added_lines[:5]:
                            parts.append(f"     ADDED: {line}")
                    
                    # Show comment changes separately
                    if added_comments or removed_comments:
                        parts.append(f"   Comment/TODO changes:")
                        for line in removed_comments[:3]:
                            parts.append(f"     REMOVED: {line}")
                        for line in added_comments[:3]:
                            parts.append(f"     ADDED: {line}")
        else:
            parts.append("\n⚠️ NO FILE CHANGES - Session captured for tracking only")
        
        # TODOs only relevant when there's actual work in progress
        if todos and files:
            parts.append(f"\nTODOs ({len(todos)}):")
            for t in todos[:3]:
                parts.append(f"  - {t.get('text')}")
        
        return "\n".join(parts)
    
    def _generate_rule_based_summary(self, capsule_data: Dict) -> str:
        files = capsule_data.get("file_changes", [])
        todos = capsule_data.get("todos", [])
        
        if not files:
            return "No code changes detected. Session captured for tracking."
        
        primary = max(files, key=lambda f: f.get('additions', 0) + f.get('deletions', 0))
        file_name = Path(primary['path']).stem
        
        parts = [f"You were working on {file_name}"]
        
        diff = primary.get('diff', '')
        funcs = re.findall(r'\+\s*def\s+(\w+)', diff)
        if funcs:
            parts.append(f"— added {', '.join(funcs[:2])}()")
        
        if todos:
            parts.append(f"Still need to: {todos[0].get('text')}")
        
        return " ".join(parts)
    
    async def generate_next_steps(self, capsule_data: Dict) -> List[str]:
        if not self.ai_available:
            return self._fallback_next_steps(capsule_data)
        
        try:
            context = self._build_context(capsule_data)
            prompt = f"""Based on this session, suggest 3-4 next steps.

{context}

Return ONLY a list with "-" prefix, like:
- Complete authentication flow
- Add unit tests
- Handle edge cases"""

            response = await self.ai_client.generate(prompt=prompt, max_tokens=150)
            steps = [line.strip('- ').strip() for line in response.split('\n') if line.strip().startswith('-')]
            return steps[:4] if steps else self._fallback_next_steps(capsule_data)
        except Exception:
            return self._fallback_next_steps(capsule_data)
    
    def _fallback_next_steps(self, capsule_data: Dict) -> List[str]:
        steps = []
        todos = capsule_data.get("todos", [])
        for t in todos[:2]:
            steps.append(t.get("text", "Complete task"))
        
        return steps[:4] if steps else ["Continue development"]
    
    async def explain_why(self, capsule_data: Dict, question: str = "") -> str:
        """Generate explanation using ALL 5 SOURCES for comprehensive understanding.
        
        Leverages:
        1. Git diffs (file_changes) - What changed
        2. Full file contents (full_file_contents) - Complete code context
        3. AST analysis (ast_analysis) - Code structure
        4. Semantic search results (semantic_results) - Related code
        5. Project metadata (project_metadata) - Dependencies & structure
        """
        if not self.ai_available:
            return self._fallback_why(capsule_data)
        
        # Check if there's any data from the 5 sources
        files = capsule_data.get("file_changes", [])
        full_file_contents = capsule_data.get("full_file_contents", {})
        ast_analysis = capsule_data.get("ast_analysis", {})
        semantic_results = capsule_data.get("semantic_results", [])
        project_metadata = capsule_data.get("project_metadata", {})
        
        # Legacy support for old file_contents field
        legacy_file_contents = capsule_data.get("file_contents", {})
        
        if not files and not full_file_contents and not legacy_file_contents:
            return "No code changes in this session - just tracking activity."
        
        try:
            # Build base context from git diffs
            context = self._build_context(capsule_data)
            
            # ============================================================
            # SOURCE 2: FULL FILE CONTENTS - Complete code understanding
            # ============================================================
            if full_file_contents:
                context += "\n\n=== FULL FILE CONTENTS (Complete Code Context) ==="
                for filepath, file_data in list(full_file_contents.items())[:3]:  # Limit to 3 files
                    context += f"\n\n📄 {filepath} ({file_data.get('lines', 0)} lines, {file_data.get('language', 'unknown')} file):"
                    content = file_data.get('content', '')
                    # Show first 100 lines to keep context manageable
                    lines = content.split('\n')[:100]
                    context += f"\n```\n" + '\n'.join(lines) + "\n```"
                    total_lines = len(content.split('\n'))
                    if total_lines > 100:
                        remaining_lines = total_lines - 100
                        context += f"\n... ({remaining_lines} more lines not shown)"
            
            # Legacy file_contents support (from ask command's manual loading)
            if legacy_file_contents and not full_file_contents:
                context += "\n\n=== FILE CONTENTS (User-requested files) ==="
                for filename, content in legacy_file_contents.items():
                    context += f"\n\n📄 {filename}:\n```\n{content}\n```"
            
            # ============================================================
            # SOURCE 3: AST ANALYSIS - Code structure understanding
            # ============================================================
            if ast_analysis:
                context += "\n\n=== CODE STRUCTURE (AST Analysis) ==="
                for filepath, ast_data in list(ast_analysis.items())[:3]:  # Limit to 3 files
                    context += f"\n\n📄 {filepath}:"
                    
                    functions = ast_data.get('functions', [])
                    if functions:
                        context += f"\n  Functions ({len(functions)}):"
                        for func in functions[:10]:  # Top 10 functions
                            decorators = func.get('decorators', [])
                            dec_str = f"@{', @'.join(decorators)}" if decorators else ""
                            async_str = "async " if func.get('is_async') else ""
                            context += f"\n    - {dec_str}{async_str}def {func['name']}() (lines {func['line_start']}-{func['line_end']})"
                    
                    classes = ast_data.get('classes', [])
                    if classes:
                        context += f"\n  Classes ({len(classes)}):"
                        for cls in classes[:5]:  # Top 5 classes
                            context += f"\n    - class {cls['name']} (lines {cls['line_start']}-{cls['line_end']})"
                            methods = cls.get('methods', [])
                            if methods:
                                for method in methods[:5]:  # Top 5 methods per class
                                    context += f"\n      - {method['name']}() (lines {method['line_start']}-{method['line_end']})"
                    
                    imports = ast_data.get('imports', [])
                    if imports:
                        context += f"\n  Imports: {', '.join(imports[:10])}"
            
            # ============================================================
            # SOURCE 4: SEMANTIC SEARCH - Related code discovery
            # ============================================================
            if semantic_results:
                context += "\n\n=== RELATED CODE (Semantic Search Results) ==="
                context += f"\nFound {len(semantic_results)} related entities in the codebase:"
                for result in semantic_results[:5]:  # Top 5 results
                    entity_type = result.get('entity_type', 'unknown')
                    entity_name = result.get('entity_name', 'unknown')
                    file_path = result.get('file_path', 'unknown')
                    relevance = result.get('relevance_score', 0)
                    ctx = result.get('context', '')
                    
                    context += f"\n  - {entity_type} '{entity_name}' in {file_path} (relevance: {relevance:.2f})"
                    if ctx:
                        # Show first 200 chars of context
                        context += f"\n    Context: {ctx[:200]}..."
            
            # ============================================================
            # SOURCE 5: PROJECT CONTEXT - Metadata & dependencies
            # ============================================================
            if project_metadata:
                context += "\n\n=== PROJECT CONTEXT (Metadata) ==="
                context += f"\nProject: {project_metadata.get('project_name', 'unknown')}"
                context += f"\nType: {project_metadata.get('project_type', 'unknown')}"
                context += f"\nFiles: {project_metadata.get('total_files', 0)} ({project_metadata.get('total_lines', 0)} lines)"
                
                dependencies = project_metadata.get('dependencies', [])
                if dependencies:
                    context += f"\nDependencies ({len(dependencies)}): "
                    dep_names = [f"{dep['name']}" for dep in dependencies[:10]]
                    context += ', '.join(dep_names)
                
                file_types = project_metadata.get('file_types', {})
                if file_types:
                    context += f"\nFile types: {dict(list(file_types.items())[:5])}"
            
            # ============================================================
            # BUILD INTELLIGENT PROMPT USING ALL SOURCES
            # ============================================================
            
            # Build a more intelligent prompt based on whether question is provided
            if question:
                # Specific question - focused analysis
                task_instruction = f'Answer this specific question: "{question}"'
                detail_instruction = """You MUST provide a DETAILED, SPECIFIC answer using the data provided.

You have access to 5 sources of truth:
1. Git diffs - what changed
2. Full file contents - COMPLETE code (use this to see ALL classes/methods/functions!)
3. AST structure - detailed code structure with line numbers
4. Semantic search - related code
5. Project metadata - dependencies

CRITICAL RULES FOR ANSWERING:
- If asked about classes/methods/functions - list them ALL from AST analysis or full file contents
- If asked about changes - cite specific diffs and line numbers
- If asked "what did I do" - describe ACTUAL changes, not generic statements
- NO vague responses like "you were building features" - be SPECIFIC
- Use actual names, line numbers, and code snippets from the sources
- If you can't find the info in the sources, say so explicitly

EXAMPLE - BAD: "You were building new features in cart.py"
EXAMPLE - GOOD: "The ShoppingCart class has these methods: add_item() (line 45), remove_item() (line 52), update_quantity() (line 60), get_total() (line 68), get_item_count() (line 72), clear() (line 76), and get_items() (line 79)"

ALWAYS cite the SOURCE you used (AST, full file, diff, etc) when answering."""
            else:
                # No question - analyze the session deeply
                task_instruction = 'Summarize what was done and what remains, like a mentor talking to a colleague.'
                detail_instruction = """Write naturally, like you're catching someone up on their work. NO markdown formatting, NO asterisks, NO structured headings.

TONE: Casual, direct, conversational - like a senior dev checking in.

You have comprehensive context from 5 sources:
- Git diffs showing changes
- Full file contents showing complete code
- AST analysis showing code structure
- Semantic search showing related code
- Project metadata showing dependencies

Use ALL sources to provide accurate, complete insights.

EXAMPLES:

✅ GOOD: "You added a basic addition function to calculator.py. Two TODOs left: adding multiplication/division and implementing user input."

✅ GOOD: "You refactored the auth module to use JWT tokens instead of sessions. Still need to add refresh token logic and test edge cases."

✅ GOOD: "You fixed the bug in the login flow where sessions weren't expiring. Next up is adding rate limiting."

❌ BAD: "**What you did:** You added..." (NO markdown formatting!)

❌ BAD: "You implemented a fundamental arithmetic operation, laying the groundwork..." (Too flowery!)

❌ BAD: "You made important changes that will improve the codebase significantly." (Too vague!)

RULES:
- Maximum 2-3 sentences
- Plain text only, no markdown, no asterisks, no formatting
- Conversational tone
- State what was done + what remains (if TODOs exist)
- No glorification, just facts"""
            
            prompt = f"""You are Brainet, a direct and concise coding assistant with COMPREHENSIVE codebase knowledge. Use "You" to address the developer.

{context}

{task_instruction}

{detail_instruction}

CRITICAL RULES:
- Maximum 3 sentences (unless answering a complex question)
- No glorification or hype
- Just facts: what was done + what's next
- List TODOs if present
- Be professional but casual, like a colleague
- USE ALL 5 SOURCES when answering - you have complete context now!
- NEVER mention where the information came from (AST, files, search, etc.) - just state facts directly like you already know them

WORD BANS: "laying groundwork", "paving the way", "enhancing capabilities", "fundamental", "revolutionary", "game-changing", "innovative", "groundbreaking", "likely", "probably", "may have", "might", "possibly", "seen in", "as listed in", "according to", "from the", "in the full file", "based on", "found in", "mentioned in", "shown in"
"""

            response = await self.ai_client.generate(prompt=prompt, max_tokens=300)  # Increased from 200 for richer answers
            return response.strip()
        except Exception:
            return self._fallback_why(capsule_data)
    
    def _fallback_why(self, capsule_data: Dict) -> str:
        files = capsule_data.get("file_changes", [])
        if not files:
            return "No code changes detected in this session."
        
        primary = max(files, key=lambda f: f.get('additions', 0))
        name = Path(primary['path']).name
        diff = primary.get('diff', '')
        
        if '+def ' in diff or '+class ' in diff:
            return f"You were building new features in {name}."
        elif 'fix' in diff or 'bug' in diff:
            return f"You were fixing bugs in {name}."
        else:
            return f"You were refactoring {name}."


class SessionSummarizerSync:
    
    def __init__(self, use_ai: bool = True):
        self.async_summarizer = SessionSummarizer(use_ai=use_ai)
    
    def generate_summary(self, capsule_data: Dict) -> str:
        return asyncio.run(self.async_summarizer.generate_summary(capsule_data))
    
    def generate_next_steps(self, capsule_data: Dict) -> List[str]:
        return asyncio.run(self.async_summarizer.generate_next_steps(capsule_data))
    
    def explain_why(self, capsule_data: Dict, question: str = "") -> str:
        return asyncio.run(self.async_summarizer.explain_why(capsule_data, question))
