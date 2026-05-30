# 🔬 PyAuditor — Universal Python Code Auditor

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Static Analysis](https://img.shields.io/badge/Static_Analysis-AST_Based-FF6F00?style=for-the-badge&logo=scrutinizer-ci&logoColor=white)](#)
[![BYOAI](https://img.shields.io/badge/AI_Audit-Bring_Your_Own_AI-8E75C2?style=for-the-badge&logo=openai&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Extra_Dependencies-Zero_(stdlib_only)-brightgreen?style=for-the-badge)](#)

> **Stop guessing. Start knowing. Every bug. Every risk. Every fix — before you ship.**

**PyAuditor** is a standalone desktop application that performs deep, two-layer analysis of any Python codebase. It combines **25-rule AST-based static analysis** with an innovative **"Bring Your Own AI" (BYOAI)** prompt generator to surface not just what will crash — but what *will go wrong*, and *why*, and *exactly how to fix it*.

Built for developers who demand zero ambiguity in their code quality.

---

## ✨ Two Layers of Analysis

### ⚡ Layer 1 — Static Scan (Instant, Offline)
Parses every `.py` file into an Abstract Syntax Tree and runs 25 specialised rules. No code is executed. Results in under 2 seconds for thousands of lines.

### 🤖 Layer 2 — AI Prompt Generator (Bring Your Own AI)
Generates an optimised, context-rich prompt wrapping your codebase. Paste it into ChatGPT, Claude 3.5, or Gemini to detect **logical errors** that no static rule can find, without worrying about API limits or privacy:
- Wrong comparison operator (`>` when `<` was intended)
- Wrong variable used (`width * width` instead of `width * height`)
- Logic contradicting comments/docstrings
- Off-by-one errors, wrong algorithms, missing edge cases

---

## 🎯 Severity Levels

| Level | Colour | Meaning |
|-------|--------|---------|
| 🔴 **CRITICAL** | Red | Will crash or produce fatal failure at runtime |
| 🟡 **WARNING** | Yellow | Runs but does the *wrong* thing silently |
| 🟠 **POTENTIAL** | Orange | Works today — time-bomb for the future |
| 🔵 **INFO** | Blue | Code quality & maintainability suggestions |
| 🟣 **LOGIC** | Purple | AI-detected logical errors (wrong behaviour, no crash) |

Every single finding includes:
- **Detail** — exactly what is technically wrong
- **Risk** — what happens at runtime if ignored (concrete scenario)
- **Fix** — exact, actionable instruction to resolve it

---

## 🖥️ Screenshots

> *Static scan + AI audit results shown side by side in the dark-mode interface.*

*(Upload your screenshot here: `![PyAuditor Screenshot](https://github.com/oguzemirtopuz/PyAuditor/raw/main/assets/screenshot.png)`)*

---

## 📋 Requirements

- **Python 3.11+** (uses `str | None` union syntax)
- **Windows / macOS / Linux** — pure `tkinter`, no platform lock-in
- **No third-party packages required** for static analysis
- **No API Keys needed** — Use your favorite LLM via the web interface

---

## 🚀 Installation & Usage

### 1. Clone the repository

```bash
git clone https://github.com/oguzemirtopuz/PyAuditor.git
cd PyAuditor
```

### 2. Run the application

```bash
python auditor_app.py
```

That's it. No `pip install`. No virtual environment. No setup.py.

### 3. (Optional) Run an AI Audit

1. Select the files you want to analyze in the UI
2. Click **📋 COPY AI PROMPT**
3. Paste the copied prompt into **ChatGPT**, **Claude**, or **Gemini**
4. The AI will instantly return a structured report of any logical errors!

### 4. Auto-Updating

Whenever a new version of PyAuditor is released, you don't need to re-download or use `git pull`. Simply run:

```bash
python update.py
```

This will automatically securely download the latest version, backup your existing files, and apply the update while protecting your local settings and history.

---

## 📁 Project Structure

```
PyAuditor/
├── auditor_app.py          # Main application — launch this
├── engine/
│   ├── __init__.py
│   ├── finding.py          # Finding dataclass (level, detail, risk, fix)
│   ├── scanner.py          # File discovery + AST parsing + rule runner
│   ├── ai_prompt.py        # BYOAI Prompt Generator
│   └── rules/
│       ├── __init__.py     # Rule registry (ALL_RULES)
│       ├── base.py         # Abstract Rule base class
│       ├── async_rules.py  # asyncio / concurrency rules
│       ├── safety_rules.py # Exception handling, mutable defaults, os._exit
│       ├── dead_code.py    # Unused params, attrs, imports, widgets
│       ├── design.py       # Long functions, nesting, type hints, docstrings
│       └── potential.py    # Magic numbers, hardcoded paths, TODO/FIXME
├── history/                # Auto-saved scan history (JSON)
```

---

## 🛠️ Rule Catalogue (25 Static Rules)

### 🔴 Critical — Async & Concurrency
| Rule ID | What it detects |
|---------|----------------|
| `asyncio_lock_race` | `asyncio.Lock` lazy-init race condition |
| `blocking_in_async` | `time.sleep` / `requests.get` / `locale.setlocale` inside `async def` |
| `missing_await` | Coroutine called without `await` — silently does nothing |
| `syntax_error` | File cannot be parsed by Python |

### 🟡 Warning — Safety
| Rule ID | What it detects |
|---------|----------------|
| `bare_except` | `except:` catches `SystemExit` and `KeyboardInterrupt` |
| `except_pass` | `except: pass` — error silently swallowed |
| `mutable_default_arg` | `def f(x=[])` — shared mutable default |
| `shadow_builtin` | Variable named `list`, `dict`, `str`, etc. |
| `os_exit_bypass` | `os._exit()` skips all Python cleanup |
| `dead_parameter` | Parameter declared but never used in body |
| `unused_self_attr` | `self.x` assigned in `__init__` but never read |
| `widget_not_packed` | Tkinter widget created but never laid out |
| `duplicate_list_items` | Duplicate constants in a list literal |

### 🟠 Potential — Future Risks
| Rule ID | What it detects |
|---------|----------------|
| `magic_number` | Unexplained numeric literal in comparisons/assignments |
| `todo_fixme` | `TODO` / `FIXME` / `HACK` / `BUG` comments |
| `hardcoded_path` | Absolute filesystem path (`C:\...`, `/home/...`) |
| `print_statement` | `print()` call bypassing the logging framework |
| `broad_exception_catch` | `except Exception` without re-raise |
| `multiword_stopword` | Space-separated stop word that can never match a tokenizer |
| `stale_log_value` | Log message references a threshold not present in code |

### 🔵 Info — Design & Quality
| Rule ID | What it detects |
|---------|----------------|
| `long_function` | Function longer than 80 lines |
| `deep_nesting` | 4+ levels of `if`/`for`/`while` nesting |
| `missing_type_hint` | Public function missing parameter or return type |
| `missing_docstring` | Public class or function missing docstring |
| `long_line` | Line longer than 120 characters |
| `unused_import` | Import never referenced in the file |

---

## ⚙️ Key Features

- **Dark-mode GUI** — professional dark theme with colour-coded severity rows
- **Interactive detail panel** — click any finding to see full Detail / Risk / Fix
- **Filter by severity** — show only CRITICAL, or only LOGIC, etc.
- **Copy for AI** — one click copies a finding in AI-ready format for Claude/Gemini/GPT
- **Open in Editor** — double-click any finding to jump to that exact line in VS Code, or any custom editor
- **Save TXT Report** — export the full report as a portable text file
- **Scan history** — each scan is saved; trend indicator shows improvement vs. last run
- **Rule toggles** — enable/disable individual rules or whole categories
- **Zero-config** — works on any Python project, no configuration files needed

---

## 🔑 Bring Your Own AI (BYOAI) Advantage

Why we removed direct API integration:
- **No API Limits/Rate Limiting:** You don't have to wait or pay for API credits.
- **Privacy First:** You manually control which code goes to the AI.
- **Model Freedom:** Want to use Claude 3.5 Sonnet for its coding excellence? Or ChatGPT for its reasoning? Just paste the prompt. The generated system prompt strictly coerces *any* modern LLM to reply in the exact PyAuditor JSON format.

---

## 🗺️ Roadmap

- [ ] JavaScript / TypeScript support (Tree-Sitter based)
- [ ] Severity threshold configuration (e.g. fail CI if CRITICAL > 0)
- [ ] GitHub Actions integration
- [ ] Diff mode — show only *new* findings vs. previous scan
- [ ] Export to JSON / HTML report

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Oğuz Emir Topuz**  
[github.com/oguzemirtopuz](https://github.com/oguzemirtopuz)

---

<div align="center">

*Built with Python's `ast` module and `tkinter`.*  
*No third-party packages required for core functionality.*

**If PyAuditor helped you ship cleaner code, consider giving it a ⭐**

</div>
