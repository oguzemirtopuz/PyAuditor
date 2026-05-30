# 🔬 PyAuditor — Universal Python Code Auditor

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Static Analysis](https://img.shields.io/badge/Static_Analysis-AST_Based-FF6F00?style=for-the-badge&logo=scrutinizer-ci&logoColor=white)](#)
[![AI Powered](https://img.shields.io/badge/AI_Audit-Gemini_2.0_Flash-8E75C2?style=for-the-badge&logo=google-gemini&logoColor=white)](https://aistudio.google.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Extra_Dependencies-Zero_(stdlib_only)-brightgreen?style=for-the-badge)](#)

> **Stop guessing. Start knowing. Every bug. Every risk. Every fix — before you ship.**

**PyAuditor** is a standalone desktop application that performs deep, two-layer analysis of any Python codebase. It combines **25-rule AST-based static analysis** with **Google Gemini AI logical reasoning** to surface not just what will crash — but what *will go wrong*, and *why*, and *exactly how to fix it*.

Built for developers who demand zero ambiguity in their code quality.

---

## ✨ Two Layers of Analysis

### ⚡ Layer 1 — Static Scan (Instant, Offline)
Parses every `.py` file into an Abstract Syntax Tree and runs 25 specialised rules. No code is executed. Results in under 2 seconds for thousands of lines.

### 🤖 Layer 2 — AI Audit (Powered by Gemini 2.0 Flash)
Sends each file to Google's Gemini API to detect **logical errors** that no static rule can find:
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

---

## 📋 Requirements

- **Python 3.11+** (uses `str | None` union syntax)
- **Windows / macOS / Linux** — pure `tkinter`, no platform lock-in
- **No third-party packages required** for static analysis
- For AI Audit: a free [Google AI Studio](https://aistudio.google.com/app/apikey) API key

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

### 3. (Optional) Enable AI Audit

1. Get a **free** API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **⚙ Settings** in PyAuditor
3. Paste the key into the **Gemini API Key** field → Save

---

## 📁 Project Structure

```
PyAuditor/
├── auditor_app.py          # Main application — launch this
├── engine/
│   ├── __init__.py
│   ├── finding.py          # Finding dataclass (level, detail, risk, fix)
│   ├── scanner.py          # File discovery + AST parsing + rule runner
│   ├── ai_audit.py         # Gemini 2.0 Flash integration
│   └── rules/
│       ├── __init__.py     # Rule registry (ALL_RULES)
│       ├── base.py         # Abstract Rule base class
│       ├── async_rules.py  # asyncio / concurrency rules
│       ├── safety_rules.py # Exception handling, mutable defaults, os._exit
│       ├── dead_code.py    # Unused params, attrs, imports, widgets
│       ├── design.py       # Long functions, nesting, type hints, docstrings
│       └── potential.py    # Magic numbers, hardcoded paths, TODO/FIXME
├── history/                # Auto-saved scan history (JSON)
└── settings.json           # Auto-created on first run
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

## 🔑 Getting a Free Gemini API Key

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with a Google account
3. Click **"Create API Key"**
4. Copy and paste into **⚙ Settings → Gemini API Key**

**Free tier limits (as of 2026):**
- 15 requests/minute
- 1,000,000 tokens/minute  
- 1,500 requests/day

PyAuditor automatically spaces requests 4 seconds apart to stay within limits.

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

*Built with Python's `ast` module, `tkinter`, and Google Gemini AI.*  
*No third-party packages required for core functionality.*

**If PyAuditor helped you ship cleaner code, consider giving it a ⭐**

</div>
