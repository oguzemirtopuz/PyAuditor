import os
from pathlib import Path

# ── System Prompt Template ─────────────
_PROMPT_TEMPLATE = """\
You are an elite Python code auditor. I am providing you with {file_count} Python file(s) from my project.

=== YOUR ONLY JOB ===
Find places where the code does THE WRONG THING — not where it is ugly, slow, or missing comments. I only care about **LOGICAL ERRORS** (bugs where the code runs without crashing but produces incorrect results or behaves in an unintended way).

=== WHAT TO LOOK FOR ===
1. Wrong comparison operator (e.g. `>` when `<` was intended)
2. Wrong variable used in math or logic
3. Logic contradicting the docstring/comment
4. Off-by-one errors in lists or loops
5. Wrong algorithm or incorrect boolean flags
6. Dead / impossible branches
7. Missing edge-case handling causing wrong results

=== WHAT NOT TO REPORT ===
Do NOT flag: syntax errors, missing type hints, unused imports, long functions, missing docstrings, style issues, or things a normal linter catches.

=== FILES TO ANALYZE ===
{files_content}

=== RESPONSE FORMAT ===
For every logical error you find, provide:
- **File:** [filename]
- **Line:** [approximate line number]
- **Issue:** [short title]
- **Detail:** [why it is wrong]
- **Fix:** [exact code to fix it]

If you find ZERO logical errors, just say: "No logical errors found. The code is structurally sound."
"""

def generate_ai_prompt(file_paths: list[str]) -> str | None:
    """
    Reads the given Python files and generates a highly optimized
    prompt to be pasted into ChatGPT, Claude, or Gemini.
    Returns None if no files could be read.
    """
    valid_files = []
    content_blocks = []
    
    for fpath in file_paths:
        try:
            path = Path(fpath)
            code = path.read_text(encoding="utf-8", errors="replace")
            # Truncate extremely large single files just in case (e.g. > 100k chars)
            if len(code) > 100_000:
                code = code[:100_000] + "\n\n# [TRUNCATED - FILE TOO LARGE]"
            
            block = f"--- START OF {path.name} ---\n```python\n{code}\n```\n--- END OF {path.name} ---\n"
            content_blocks.append(block)
            valid_files.append(fpath)
        except Exception:
            continue
            
    if not content_blocks:
        return None
        
    files_content = "\n".join(content_blocks)
    
    # Check overall size — if it exceeds ~150k chars, warn the user indirectly 
    # by adding a note at the top of the prompt. (150k chars is ~35k tokens, 
    # well within ChatGPT/Claude limits, but good to know).
    prompt = _PROMPT_TEMPLATE.format(
        file_count=len(valid_files),
        files_content=files_content
    )
    
    if len(prompt) > 200_000:
        prompt = "NOTE: This prompt is very large. You may need a model with a 100K+ context window (like Claude 3.5 Sonnet or Gemini 1.5 Pro).\n\n" + prompt
        
    return prompt
