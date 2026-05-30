"""
AI Audit Engine — Gemini 2.0 Flash Integration
================================================
Sends Python source files to Google Gemini for LOGICAL error detection.
Detects errors that static analysis (AST) cannot find:
  - Wrong conditions (> when < was intended)
  - Wrong variable used
  - Logic contradicting comments/docstrings
  - Off-by-one errors
  - Wrong algorithm (finds minimum when it should find maximum)
  - Dead branches / unreachable code
  - Missing edge cases (empty list, zero division, None)
  - Wrong return values / missing returns in branches
"""

import json
import urllib.request
import urllib.error
import time
from pathlib import Path

from engine.finding import Finding

# ── Gemini API ────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL   = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# ── System Prompt (crafted for precision, low false-positive rate) ─────────────
_SYSTEM_PROMPT = """\
You are a world-class Python code reviewer who specialises EXCLUSIVELY in
LOGICAL errors — bugs where the code runs without crashing but produces
incorrect results or behaves in an unintended way.

=== YOUR ONLY JOB ===
Find places where the code does THE WRONG THING — not where it is ugly,
slow, or missing comments. Logic bugs only.

=== WHAT TO LOOK FOR (examples) ===
1. Wrong comparison operator: `if x > threshold` when it should be `<`
2. Wrong variable used: multiplied `width * width` instead of `width * height`
3. Logic contradicts the docstring/comment: comment says "returns sorted list"
   but the function returns the original unsorted list
4. Off-by-one: `range(n)` where `range(n+1)` is needed, or `[:-1]` cutting
   the last valid element
5. Wrong algorithm: a loop that claims to find the maximum but actually finds
   the minimum (wrong comparison inside)
6. Incorrect flag/state: a boolean flag set to `True` when the intent is `False`
7. Dead / impossible branch: a condition that can never be True given the
   surrounding context (e.g. `if x > 10 and x < 5`)
8. Missing edge-case handling causing wrong results: e.g. an empty list
   returning 0 when it should return None, or a division where the denominator
   is computed but can be zero
9. Wrong order of operations changing the computed value
10. Missing `return` in one branch of a function that should always return a value

=== WHAT NOT TO REPORT ===
Do NOT flag: syntax errors, missing type hints, unused imports, long functions,
missing docstrings, style issues, `print()` calls, or anything a linter catches.
Only report things that cause WRONG BEHAVIOUR at runtime.

=== STRICT OUTPUT FORMAT ===
Respond ONLY with a valid JSON array. No introduction, no explanation, no
markdown fences outside the JSON.

[
  {
    "line": <integer — the most relevant line number>,
    "title": "<max 80 chars — what the bug is>",
    "detail": "<what the code currently does vs. what it should do>",
    "risk": "<what goes wrong at runtime if this is not fixed — be concrete>",
    "fix": "<exact, actionable fix instruction with the corrected code snippet>"
  }
]

If you find ZERO logical errors, respond with exactly: []
"""

_USER_TEMPLATE = """\
Analyze the following Python file for LOGICAL errors only.

File: {filename}
Lines: {line_count}

```python
{code}
```

Respond with the JSON array only.
"""

# Token limit — roughly 120k chars ≈ ~30k tokens, well within free limits
MAX_FILE_CHARS = 120_000


# ══════════════════════════════════════════════════════════════════════════════
def _call_gemini(api_key: str, prompt: str) -> str:
    """Raw HTTP call to Gemini generateContent endpoint. Returns response text."""
    url  = f"{GEMINI_URL}?key={api_key}"
    body = json.dumps({
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.1,   # Low temp → focused, deterministic output
            "topP":            0.9,
            "maxOutputTokens": 4096,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # Extract text from Gemini response structure
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_response(text: str) -> list[dict]:
    """Extract JSON array from Gemini response text."""
    text = text.strip()
    # Strip optional markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text  = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    text = text.strip()
    if not text or text == "[]":
        return []
    return json.loads(text)


def analyze_file(
    api_key: str,
    file_path: str,
    delay: float = 4.0,
) -> tuple[list[Finding], str | None]:
    """
    Send one Python file to Gemini for logical error analysis.

    Parameters
    ----------
    api_key   : Gemini API key (from Google AI Studio)
    file_path : Absolute path to the .py file
    delay     : Seconds to wait AFTER the call (rate-limit buffer)

    Returns
    -------
    (findings, error_message)
    error_message is None on success, a string description on failure.
    """
    try:
        path = Path(file_path)
        code = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [], f"Cannot read {file_path}: {e}"

    if len(code) > MAX_FILE_CHARS:
        code = code[:MAX_FILE_CHARS] + "\n\n# [TRUNCATED — file too large]"

    prompt  = _USER_TEMPLATE.format(
        filename   = path.name,
        line_count = len(code.splitlines()),
        code       = code,
    )

    try:
        raw     = _call_gemini(api_key, prompt)
        records = _parse_response(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 429:
            return [], "Rate limit hit — wait 60 seconds and try again."
        if e.code == 400:
            return [], f"Bad request (API key invalid or prompt too large): {body[:200]}"
        return [], f"HTTP {e.code}: {body[:200]}"
    except urllib.error.URLError as e:
        return [], f"Network error: {e.reason}"
    except json.JSONDecodeError as e:
        return [], f"Gemini returned invalid JSON: {e}"
    except Exception as e:
        return [], f"Unexpected error: {e}"
    finally:
        if delay > 0:
            time.sleep(delay)

    findings = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        findings.append(Finding(
            level    = "LOGIC",
            rule_id  = "ai_logical_error",
            file     = file_path,
            line     = rec.get("line", "?"),
            title    = rec.get("title",  "Logical Error Detected by AI"),
            detail   = rec.get("detail", ""),
            risk     = rec.get("risk",   ""),
            fix      = rec.get("fix",    ""),
            category = "AI",
        ))

    return findings, None


def analyze_files(
    api_key: str,
    file_paths: list[str],
    progress_cb=None,
) -> tuple[list[Finding], list[str]]:
    """
    Analyze multiple files sequentially with rate-limit spacing.

    progress_cb(file_path, index, total, status_msg) — called after each file.
    """
    all_findings: list[Finding] = []
    errors: list[str] = []
    total = len(file_paths)

    for idx, fpath in enumerate(file_paths):
        if progress_cb:
            progress_cb(fpath, idx + 1, total, "Sending to Gemini…")

        findings, err = analyze_file(api_key, fpath, delay=4.0)
        all_findings.extend(findings)
        if err:
            errors.append(f"{Path(fpath).name}: {err}")

        if progress_cb:
            status = f"{len(findings)} logical issues found" if not err else f"Error: {err[:60]}"
            progress_cb(fpath, idx + 1, total, status)

    return all_findings, errors
