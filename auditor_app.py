"""
PyAuditor — Universal Python Code Auditor
==========================================
A standalone desktop tool that scans any Python project for bugs,
anti-patterns, and potential future issues. All findings are
categorised as CRITICAL / WARNING / POTENTIAL / INFO with exact
fix instructions and a risk description for each.

Usage:
    python auditor_app.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import sys
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

# ── Make sure the engine package is importable regardless of cwd ──────────────
sys.path.insert(0, str(Path(__file__).parent))

from engine.scanner import Scanner, ScanResult, collect_python_files
from engine.finding import Finding, LEVEL_COLORS
from engine.rules import ALL_RULES, CATEGORIES
from engine.ai_prompt import generate_ai_prompt

# ── Paths ─────────────────────────────────────────────────────────────────────
APP_DIR      = Path(__file__).parent
HISTORY_DIR  = APP_DIR / "history"
SETTINGS_FILE = APP_DIR / "settings.json"
HISTORY_DIR.mkdir(exist_ok=True)

# ── Default settings ───────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "editor": "vscode",          # vscode | system | custom
    "custom_editor_cmd": "",     # e.g. "notepad++.exe {file}:{line}"
    "theme": "dark",
}

# ── Colour palette ─────────────────────────────────────────────────────────────
BG_MAIN   = "#0D1117"
BG_PANEL  = "#161B22"
BG_CARD   = "#1C2230"
BG_INPUT  = "#0F1620"
ACCENT    = "#238636"
ACCENT_H  = "#2EA043"
TEXT_MAIN = "#E6EDF3"
TEXT_DIM  = "#6E7681"
TEXT_HEAD = "#58A6FF"
BORDER    = "#30363D"

LVL_COLOR = {
    "CRITICAL":  "#FF4C4C",
    "WARNING":   "#FFB347",
    "POTENTIAL": "#FF8C00",
    "INFO":      "#5BC0EB",
    "LOGIC":     "#BF5AF2",
}
LVL_BG = {
    "CRITICAL":  "#2D0808",
    "WARNING":   "#2A1800",
    "POTENTIAL": "#1E1000",
    "INFO":      "#00111E",
    "LOGIC":     "#1A0A2E",
}
LVL_TAG = {
    "CRITICAL":  "crit",
    "WARNING":   "warn",
    "POTENTIAL": "pot",
    "INFO":      "info",
    "LOGIC":     "logic",
}


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS MANAGER
# ══════════════════════════════════════════════════════════════════════════════
class Settings:
    def __init__(self):
        self._data = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                self._data.update(json.loads(SETTINGS_FILE.read_text()))
            except Exception:
                pass

    def save(self):
        SETTINGS_FILE.write_text(json.dumps(self._data, indent=2))

    def __getitem__(self, key):
        return self._data.get(key, DEFAULT_SETTINGS.get(key))

    def __setitem__(self, key, value):
        self._data[key] = value


# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY MANAGER
# ══════════════════════════════════════════════════════════════════════════════
class HistoryManager:
    def save(self, paths: list[str], result: ScanResult):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        record = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scanned_paths": paths,
            "total_files": result.files_scanned,
            "total_lines": result.lines_scanned,
            "duration_seconds": round(result.duration, 2),
            "findings": result.counts,
        }
        out = HISTORY_DIR / f"{ts}.json"
        out.write_text(json.dumps(record, indent=2))

    def last_two(self) -> list[dict]:
        files = sorted(HISTORY_DIR.glob("*.json"))
        records = []
        for f in files[-2:]:
            try:
                records.append(json.loads(f.read_text()))
            except Exception:
                pass
        return records

    def trend_text(self) -> str:
        records = self.last_two()
        if len(records) < 2:
            return ""
        prev, last = records[0]["findings"], records[1]["findings"]
        parts = []
        for lvl in ["CRITICAL", "WARNING", "POTENTIAL", "INFO"]:
            delta = last.get(lvl, 0) - prev.get(lvl, 0)
            if delta != 0:
                arrow = "▲" if delta > 0 else "▼"
                parts.append(f"{lvl} {arrow}{abs(delta)}")
        if not parts:
            return "No change from last scan"
        return "vs. prev:  " + "   ".join(parts)

# ══════════════════════════════════════════════════════════════════════════════
#  INFO DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class InfoDialog(tk.Toplevel):
    """Full explanation of how PyAuditor works and what each severity level means."""

    _SECTIONS = [
        {
            "title": "🔌  How PyAuditor Works",
            "color": "#58A6FF",
            "body": (
                "PyAuditor analyses your Python source code in two complementary ways:\n\n"
                "1. STATIC SCAN  (▶ SCAN button)\n"
                "   Reads every .py file you select and builds a structural map of\n"
                "   the code (called an Abstract Syntax Tree / AST). It then runs\n"
                "   25 specialised rules over this map to find bugs, anti-patterns\n"
                "   and dangerous code without ever executing the code.\n"
                "   This is instant — thousands of lines in under 2 seconds.\n\n"
                "2. COPY AI PROMPT  (📋 Copy AI Prompt button)\n"
                "   Generates an optimised prompt containing your code and strict\n"
                "   instructions to find logical errors. You paste it into ChatGPT/Claude\n"
                "   to catch errors rules cannot: wrong conditions, wrong algorithms, etc."
            ),
        },
        {
            "title": "🔴  CRITICAL",
            "color": LVL_COLOR["CRITICAL"],
            "body": (
                "Your program WILL crash or produce a fatal failure because of this.\n\n"
                "Examples:\n"
                "  • asyncio.Lock created lazily inside an async function → two coroutines\n"
                "    run simultaneously, corrupting shared data.\n"
                "  • time.sleep() called inside an async function → the entire event\n"
                "    loop freezes, all other tasks stall.\n"
                "  • A coroutine called without 'await' → it silently does nothing.\n"
                "  • Syntax error → Python refuses to import the file at all.\n\n"
                "Action: Fix these FIRST. Do not run the project until they are gone."
            ),
        },
        {
            "title": "🟡  WARNING",
            "color": LVL_COLOR["WARNING"],
            "body": (
                "The program runs, but it does the WRONG thing silently.\n\n"
                "Examples:\n"
                "  • except: pass → an error is caught and thrown away. You will\n"
                "    never know the operation failed.\n"
                "  • def f(x=[]) → all callers share the same list. Mutating it in\n"
                "    one call affects every future call.\n"
                "  • os._exit() → all Python cleanup is skipped: files are not closed,\n"
                "    databases are not saved, async tasks are abandoned mid-write.\n"
                "  • Unused parameter → callers think they control behaviour, they don\'t.\n\n"
                "Action: Fix these soon. They cause hard-to-debug runtime surprises."
            ),
        },
        {
            "title": "🟠  POTENTIAL",
            "color": LVL_COLOR["POTENTIAL"],
            "body": (
                "The code works today, but contains a time-bomb for the future.\n\n"
                "Examples:\n"
                "  • Hardcoded path C:\\Users\\proog\\... → works only on your machine.\n"
                "    Deploy it elsewhere and it crashes instantly.\n"
                "  • Magic number 900 with no name → in 3 months you won\'t remember\n"
                "    if it\'s seconds, pixels, or a database limit.\n"
                "  • TODO/FIXME comment → known incomplete or broken code.\n"
                "  • 80-line function → as it grows, hiding a bug inside becomes easy.\n\n"
                "Action: Address these before the project grows larger."
            ),
        },
        {
            "title": "🔵  INFO",
            "color": LVL_COLOR["INFO"],
            "body": (
                "Code quality and maintainability suggestions. Nothing will break today,\n"
                "but these make the code harder to read, test, and extend over time.\n\n"
                "Examples:\n"
                "  • Missing docstring → future contributors (including you in 6 months)\n"
                "    have no explanation of what a function does.\n"
                "  • Missing type hints → IDEs cannot help you catch type mismatches.\n"
                "  • Unused import → slows startup time, clutters the namespace.\n"
                "  • Line > 120 chars → requires horizontal scrolling to read.\n\n"
                "Action: Address these during code review or refactoring sessions."
            ),
        },
        {
            "title": "🟣  LOGIC  (AI-detected)",
            "color": LVL_COLOR["LOGIC"],
            "body": (
                "Found by an AI assistant. The code runs and produces a result, but the\n"
                "result is WRONG because the logic is incorrect.\n\n"
                "Examples (things no static rule can detect):\n"
                "  • if x > threshold: → should be < threshold. Program accepts\n"
                "    what it should reject and rejects what it should accept.\n"
                "  • width * width instead of width * height → always wrong area.\n"
                "  • Comment says 'returns sorted list' but function returns the\n"
                "    original unsorted list.\n"
                "  • Loop finds minimum value but is named 'find_maximum'.\n\n"
                "Action: Review carefully. AI can occasionally be wrong — always\n"
                "read the Detail and verify against your code before changing."
            ),
        },
        {
            "title": "⌨️  Quick Usage Guide",
            "color": "#58A6FF",
            "body": (
                "1. Click '+ Folder' or '+ File' to add your Python project.\n"
                "2. Click '▶ SCAN' for instant static analysis (free, offline, fast).\n"
                "3. Click on any finding in the table to see the full detail below:\n"
                "     Detail  — exactly what is wrong\n"
                "     Risk    — what happens at runtime if you ignore this\n"
                "     Fix     — exact instruction to solve it\n"
                "4. Double-click a finding to open that file in your editor.\n"
                "5. Click '📋 Copy for AI' to copy one finding and paste to an AI assistant.\n"
                "6. Click '📋 Copy AI Prompt' and paste it to ChatGPT/Claude for logic analysis.\n"
                "7. Click '📄 Save TXT Report' to save the full report to a text file.\n\n"
                "Tip: Run SCAN first (it's instant), fix CRITICAL and WARNING issues,\n"
                "then use the AI Prompt on the cleaned-up code for best results."
            ),
        },
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("PyAuditor — How It Works")
        self.configure(bg=BG_MAIN)
        self.geometry("720x680")
        self.resizable(True, True)
        self.grab_set()

        # Header
        hdr = tk.Frame(self, bg=BG_PANEL, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔌  PyAuditor — How It Works",
                 font=("Segoe UI", 14, "bold"), fg=TEXT_HEAD,
                 bg=BG_PANEL).pack(side="left", padx=16)
        tk.Button(hdr, text="✕  Close", bg=BG_CARD, fg=TEXT_DIM,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self.destroy, padx=10).pack(side="right", padx=12)

        # Scrollable content
        outer = tk.Frame(self, bg=BG_MAIN)
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        canvas = tk.Canvas(outer, bg=BG_MAIN, bd=0, highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG_MAIN)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scroll
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), self.destroy()))

        # Render sections
        for sec in self._SECTIONS:
            self._render_section(inner, sec["title"], sec["color"], sec["body"])

        # Bottom close button
        tk.Button(inner, text="Close", bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold"), padx=20, pady=6,
                  command=lambda: (canvas.unbind_all("<MouseWheel>"), self.destroy())
                  ).pack(pady=(8, 16))

    def _render_section(self, parent, title: str, color: str, body: str):
        """Render one info section card."""
        card = tk.Frame(parent, bg=BG_CARD, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="x", padx=16, pady=(10, 0))

        # Coloured left border effect via a thin frame
        accent_bar = tk.Frame(card, bg=color, width=4)
        accent_bar.pack(side="left", fill="y")

        content = tk.Frame(card, bg=BG_CARD)
        content.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        tk.Label(content, text=title, fg=color, bg=BG_CARD,
                 font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")

        tk.Label(content, text=body, fg=TEXT_MAIN, bg=BG_CARD,
                 font=("Segoe UI", 9), justify="left", anchor="w",
                 wraplength=620).pack(fill="x", pady=(4, 0))


# ══════════════════════════════════════════════════════════════════════════════
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings: Settings):
        super().__init__(parent)
        self.settings = settings
        self.title("Settings")
        self.configure(bg=BG_MAIN)
        self.resizable(False, False)
        self.grab_set()

        pad = {"padx": 16, "pady": 8}

        tk.Label(self, text="Settings", font=("Segoe UI", 13, "bold"),
                 fg=TEXT_HEAD, bg=BG_MAIN).pack(**pad, anchor="w")

        # ── Editor selection ────────────────────────────────────────────────
        frm = tk.Frame(self, bg=BG_PANEL, pady=10, padx=14)
        frm.pack(fill="x", padx=14, pady=(0, 8))

        tk.Label(frm, text="Editor for 'Open in Editor'",
                 fg=TEXT_MAIN, bg=BG_PANEL, font=("Segoe UI", 10)).pack(anchor="w")

        self._editor_var = tk.StringVar(value=settings["editor"])
        for val, label in [("vscode", "VS Code  (code --goto file:line)"),
                           ("system", "System default (opens with associated app)"),
                           ("custom", "Custom command")]:
            tk.Radiobutton(frm, text=label, variable=self._editor_var, value=val,
                           fg=TEXT_MAIN, bg=BG_PANEL, selectcolor=BG_CARD,
                           activebackground=BG_PANEL, activeforeground=TEXT_MAIN,
                           command=self._on_editor_change).pack(anchor="w", pady=1)

        tk.Label(frm, text="Custom command  (use {file} and {line} as placeholders):",
                 fg=TEXT_DIM, bg=BG_PANEL, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))
        self._custom_entry = tk.Entry(frm, bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                                      relief="flat", font=("Consolas", 10), width=46)
        self._custom_entry.insert(0, settings["custom_editor_cmd"])
        self._custom_entry.pack(anchor="w", pady=2, ipady=4)
        self._on_editor_change()

        # Buttons
        btn_frame = tk.Frame(self, bg=BG_MAIN)
        btn_frame.pack(fill="x", padx=14, pady=10)
        tk.Button(btn_frame, text="Save", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=16, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")
        tk.Button(btn_frame, text="Cancel", bg=BG_CARD, fg=TEXT_MAIN, relief="flat",
                  font=("Segoe UI", 10), padx=16, pady=6,
                  cursor="hand2", command=self.destroy).pack(side="right", padx=(0, 6))

    def _on_editor_change(self):
        state = "normal" if self._editor_var.get() == "custom" else "disabled"
        self._custom_entry.configure(state=state)

    def _save(self):
        self.settings["editor"] = self._editor_var.get()
        self.settings.save()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
class PyAuditorApp:
    def __init__(self):
        self.settings = Settings()
        self.history  = HistoryManager()
        self._scan_result: ScanResult | None = None
        self._scan_paths: list[str] = []
        self._ai_findings: list[Finding] = []   # AI logical error findings
        self._all_findings: list[Finding] = []  # static + AI combined

        self.root = tk.Tk()
        self.root.title("PyAuditor — Universal Python Code Auditor")
        self.root.configure(bg=BG_MAIN)
        self.root.geometry("1280x800")
        self.root.minsize(900, 600)

        self._style_ttk()
        self._build_ui()
        self._refresh_trend()

    # ── TTK Styling ────────────────────────────────────────────────────────────
    def _style_ttk(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview",
                         background=BG_CARD, foreground=TEXT_MAIN,
                         fieldbackground=BG_CARD, rowheight=26,
                         font=("Consolas", 10), borderwidth=0)
        style.configure("Treeview.Heading",
                         background=BG_PANEL, foreground=TEXT_HEAD,
                         font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Treeview",
                  background=[("selected", "#1F4D88")],
                  foreground=[("selected", "white")])
        style.configure("Vertical.TScrollbar",
                         background=BG_CARD, troughcolor=BG_MAIN,
                         borderwidth=0, arrowcolor=TEXT_DIM)
        style.configure("TProgressbar",
                         troughcolor=BG_CARD, background=ACCENT)

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top bar
        topbar = tk.Frame(self.root, bg=BG_PANEL, height=48)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="🔬 PyAuditor", font=("Segoe UI", 14, "bold"),
                 fg=TEXT_HEAD, bg=BG_PANEL).pack(side="left", padx=16)
        tk.Label(topbar, text="Universal Python Code Auditor",
                 font=("Segoe UI", 10), fg=TEXT_DIM, bg=BG_PANEL).pack(side="left")
        tk.Button(topbar, text="ℹ Info", bg=BG_CARD, fg=TEXT_HEAD,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
                  command=self._open_info, padx=10, pady=4).pack(side="right", padx=(0, 4), pady=8)
        tk.Button(topbar, text="⚙ Settings", bg=BG_CARD, fg=TEXT_DIM,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._open_settings, padx=10, pady=4).pack(side="right", padx=12, pady=8)

        # Main paned layout
        paned = tk.PanedWindow(self.root, orient="horizontal",
                                bg=BG_MAIN, sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # Left panel
        left = tk.Frame(paned, bg=BG_PANEL, width=300)
        paned.add(left, minsize=260)
        self._build_left_panel(left)

        # Right panel
        right = tk.Frame(paned, bg=BG_MAIN)
        paned.add(right, minsize=500)
        self._build_right_panel(right)

        # Bottom status bar
        self._build_statusbar()

    def _build_left_panel(self, parent):
        # Title
        tk.Label(parent, text="SCAN TARGETS", font=("Segoe UI", 9, "bold"),
                 fg=TEXT_DIM, bg=BG_PANEL).pack(anchor="w", padx=14, pady=(14, 4))

        # Add buttons
        btn_frame = tk.Frame(parent, bg=BG_PANEL)
        btn_frame.pack(fill="x", padx=10, pady=(0, 6))
        tk.Button(btn_frame, text="+ Folder", bg=BG_CARD, fg=TEXT_MAIN,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._add_folder, padx=8, pady=4).pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="+ File", bg=BG_CARD, fg=TEXT_MAIN,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._add_file, padx=8, pady=4).pack(side="left")
        tk.Button(btn_frame, text="Clear All", bg=BG_CARD, fg=TEXT_DIM,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._clear_targets, padx=8, pady=4).pack(side="right")

        # Target list
        list_frame = tk.Frame(parent, bg=BG_INPUT, highlightthickness=1,
                              highlightbackground=BORDER)
        list_frame.pack(fill="both", expand=False, padx=10, pady=(0, 8))
        self._target_listbox = tk.Listbox(
            list_frame, bg=BG_INPUT, fg=TEXT_MAIN, selectbackground="#1F4D88",
            relief="flat", font=("Consolas", 9), height=7, bd=0,
            activestyle="none"
        )
        self._target_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._target_listbox.bind("<Delete>", self._remove_selected_target)
        self._target_listbox.bind("<BackSpace>", self._remove_selected_target)

        # Rules section
        tk.Label(parent, text="RULES", font=("Segoe UI", 9, "bold"),
                 fg=TEXT_DIM, bg=BG_PANEL).pack(anchor="w", padx=14, pady=(4, 4))

        # Category quick filters
        cat_frame = tk.Frame(parent, bg=BG_PANEL)
        cat_frame.pack(fill="x", padx=10, pady=(0, 4))
        tk.Button(cat_frame, text="All ON", bg=BG_CARD, fg=ACCENT_H,
                  relief="flat", cursor="hand2", font=("Segoe UI", 8),
                  command=lambda: self._set_all_rules(True),
                  padx=6, pady=2).pack(side="left", padx=(0, 3))
        tk.Button(cat_frame, text="All OFF", bg=BG_CARD, fg=TEXT_DIM,
                  relief="flat", cursor="hand2", font=("Segoe UI", 8),
                  command=lambda: self._set_all_rules(False),
                  padx=6, pady=2).pack(side="left")

        # Scrollable rule list
        rules_outer = tk.Frame(parent, bg=BG_INPUT, highlightthickness=1,
                               highlightbackground=BORDER)
        rules_outer.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        canvas = tk.Canvas(rules_outer, bg=BG_INPUT, bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(rules_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        rules_inner = tk.Frame(canvas, bg=BG_INPUT)
        canvas.create_window((0, 0), window=rules_inner, anchor="nw")
        rules_inner.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self._rule_vars: dict[str, tk.BooleanVar] = {}
        current_cat = None
        for rule in ALL_RULES:
            if rule.category != current_cat:
                current_cat = rule.category
                tk.Label(rules_inner, text=f"── {current_cat} ──",
                         fg=TEXT_DIM, bg=BG_INPUT,
                         font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6, pady=(6, 0))
            var = tk.BooleanVar(value=True)
            self._rule_vars[rule.rule_id] = var
            lvl_col = LVL_COLOR.get(
                "CRITICAL" if rule.category == "Async" else
                "WARNING"  if rule.category in ("Safety", "DeadCode") else
                "POTENTIAL" if rule.category == "Potential" else "INFO",
                TEXT_DIM
            )
            cb = tk.Checkbutton(
                rules_inner, text=rule.rule_id,
                variable=var, fg=lvl_col, bg=BG_INPUT,
                selectcolor=BG_CARD, activebackground=BG_INPUT,
                activeforeground=lvl_col, font=("Consolas", 9),
                anchor="w"
            )
            cb.pack(fill="x", padx=6, pady=0)

        # Scan button
        self._scan_btn = tk.Button(
            parent, text="▶  SCAN", bg=ACCENT, fg="white",
            relief="flat", cursor="hand2",
            font=("Segoe UI", 12, "bold"),
            command=self._start_scan, pady=10
        )
        self._scan_btn.pack(fill="x", padx=10, pady=(0, 4))

        # AI Audit button
        self._ai_btn = tk.Button(
            parent, text="📋  COPY AI PROMPT",
            bg="#2D1454", fg=LVL_COLOR["LOGIC"],
            relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            command=self._start_ai_audit, pady=10
        )
        self._ai_btn.pack(fill="x", padx=10, pady=(0, 8))

        # Progress bar
        self._progress = ttk.Progressbar(parent, mode="indeterminate")
        self._progress.pack(fill="x", padx=10, pady=(0, 8))

    def _build_right_panel(self, parent):
        # Summary counters
        counter_frame = tk.Frame(parent, bg=BG_PANEL, height=52)
        counter_frame.pack(fill="x")
        counter_frame.pack_propagate(False)

        self._counter_labels: dict[str, tk.Label] = {}
        for lvl in ["CRITICAL", "WARNING", "POTENTIAL", "INFO", "LOGIC"]:
            box = tk.Frame(counter_frame, bg=LVL_BG[lvl], padx=10, pady=4)
            box.pack(side="left", padx=(8, 0), pady=8)
            lbl = tk.Label(box, text=f"{lvl}\n0",
                           fg=LVL_COLOR[lvl], bg=LVL_BG[lvl],
                           font=("Segoe UI", 9, "bold"), justify="center")
            lbl.pack()
            self._counter_labels[lvl] = lbl

        # Filter buttons
        filter_frame = tk.Frame(parent, bg=BG_MAIN)
        filter_frame.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(filter_frame, text="Show:", fg=TEXT_DIM, bg=BG_MAIN,
                 font=("Segoe UI", 9)).pack(side="left")
        self._filter_var = tk.StringVar(value="ALL")
        for lbl in ["ALL", "CRITICAL", "WARNING", "POTENTIAL", "INFO", "LOGIC"]:
            col = LVL_COLOR.get(lbl, TEXT_DIM)
            tk.Radiobutton(filter_frame, text=lbl, variable=self._filter_var,
                           value=lbl, fg=col, bg=BG_MAIN, selectcolor=BG_CARD,
                           activebackground=BG_MAIN, activeforeground=col,
                           font=("Segoe UI", 9), command=self._apply_filter
                           ).pack(side="left", padx=4)

        # Results treeview
        tree_frame = tk.Frame(parent, bg=BG_MAIN)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=6)

        cols = ("Level", "File", "Line", "Title")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                   selectmode="browse")
        self._tree.heading("Level", text="Level",
                            command=lambda: self._sort_col("Level"))
        self._tree.heading("File",  text="File",
                            command=lambda: self._sort_col("File"))
        self._tree.heading("Line",  text="Line",
                            command=lambda: self._sort_col("Line"))
        self._tree.heading("Title", text="Title",
                            command=lambda: self._sort_col("Title"))
        self._tree.column("Level", width=90,  minwidth=80,  anchor="center")
        self._tree.column("File",  width=260, minwidth=120, anchor="w")
        self._tree.column("Line",  width=55,  minwidth=45,  anchor="center")
        self._tree.column("Title", width=500, minwidth=200, anchor="w")

        for lvl, tag in LVL_TAG.items():
            self._tree.tag_configure(tag,
                                      foreground=LVL_COLOR[lvl],
                                      background=LVL_BG[lvl])
        # LOGIC tag (AI findings)
        self._tree.tag_configure("logic",
                                  foreground=LVL_COLOR["LOGIC"],
                                  background=LVL_BG["LOGIC"])

        vsb_tree = ttk.Scrollbar(tree_frame, orient="vertical",
                                  command=self._tree.yview)
        hsb_tree = ttk.Scrollbar(tree_frame, orient="horizontal",
                                  command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb_tree.set,
                              xscrollcommand=hsb_tree.set)
        vsb_tree.pack(side="right", fill="y")
        hsb_tree.pack(side="bottom", fill="x")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Double-1>", self._open_in_editor)

        # Detail panel
        detail_outer = tk.Frame(parent, bg=BG_CARD, height=200,
                                 highlightthickness=1, highlightbackground=BORDER)
        detail_outer.pack(fill="x", padx=8, pady=(0, 6))
        detail_outer.pack_propagate(False)

        # Detail header
        dh = tk.Frame(detail_outer, bg=BG_CARD)
        dh.pack(fill="x", padx=10, pady=(8, 0))
        self._detail_title = tk.Label(dh, text="Select a finding to see details",
                                       fg=TEXT_HEAD, bg=BG_CARD,
                                       font=("Segoe UI", 10, "bold"),
                                       wraplength=700, justify="left")
        self._detail_title.pack(side="left", fill="x", expand=True)

        # Action buttons
        act = tk.Frame(dh, bg=BG_CARD)
        act.pack(side="right")
        self._copy_btn = tk.Button(act, text="📋 Copy for AI", bg=BG_PANEL,
                                    fg=TEXT_MAIN, relief="flat", cursor="hand2",
                                    font=("Segoe UI", 9), padx=8, pady=3,
                                    command=self._copy_finding)
        self._copy_btn.pack(side="left", padx=(0, 4))
        self._edit_btn = tk.Button(act, text="🔗 Open in Editor", bg=BG_PANEL,
                                    fg=TEXT_MAIN, relief="flat", cursor="hand2",
                                    font=("Segoe UI", 9), padx=8, pady=3,
                                    command=self._open_in_editor)
        self._edit_btn.pack(side="left")

        # Detail text area
        self._detail_text = scrolledtext.ScrolledText(
            detail_outer, bg=BG_CARD, fg=TEXT_MAIN, relief="flat",
            font=("Consolas", 10), wrap="word", state="disabled",
            height=8, padx=10, pady=6,
            insertbackground=TEXT_MAIN
        )
        self._detail_text.pack(fill="both", expand=True, padx=4, pady=(4, 8))
        # Configure text tags
        self._detail_text.tag_configure("label",  foreground=TEXT_DIM,
                                         font=("Segoe UI", 9, "bold"))
        self._detail_text.tag_configure("body",   foreground=TEXT_MAIN,
                                         font=("Consolas", 10))
        self._detail_text.tag_configure("fix",    foreground="#3FB950",
                                         font=("Consolas", 10))
        self._detail_text.tag_configure("risk",   foreground=LVL_COLOR["WARNING"],
                                         font=("Consolas", 10))
        self._detail_text.tag_configure("crit_h", foreground=LVL_COLOR["CRITICAL"],
                                         font=("Segoe UI", 10, "bold"))
        self._detail_text.tag_configure("warn_h", foreground=LVL_COLOR["WARNING"],
                                         font=("Segoe UI", 10, "bold"))
        self._detail_text.tag_configure("pot_h",  foreground=LVL_COLOR["POTENTIAL"],
                                         font=("Segoe UI", 10, "bold"))
        self._detail_text.tag_configure("info_h",  foreground=LVL_COLOR["INFO"],
                                         font=("Segoe UI", 10, "bold"))
        self._detail_text.tag_configure("logic_h", foreground=LVL_COLOR["LOGIC"],
                                         font=("Segoe UI", 10, "bold"))

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=BG_PANEL, height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._status_lbl = tk.Label(bar, text="Ready — add folders or files, then click SCAN",
                                     fg=TEXT_DIM, bg=BG_PANEL,
                                     font=("Segoe UI", 9))
        self._status_lbl.pack(side="left", padx=12)

        self._trend_lbl = tk.Label(bar, text="",
                                    fg=TEXT_DIM, bg=BG_PANEL,
                                    font=("Segoe UI", 9))
        self._trend_lbl.pack(side="right", padx=12)

        # Bottom action buttons
        btn_bar = tk.Frame(self.root, bg=BG_PANEL)
        btn_bar.pack(fill="x", side="bottom")
        tk.Button(btn_bar, text="📄 Save TXT Report", bg=BG_CARD, fg=TEXT_MAIN,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._save_report, padx=10, pady=4).pack(side="left", padx=8, pady=4)
        tk.Button(btn_bar, text="📋 Copy All Findings", bg=BG_CARD, fg=TEXT_MAIN,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._copy_all, padx=10, pady=4).pack(side="left", padx=(0, 8), pady=4)
        tk.Button(btn_bar, text="🗑 Clear Results", bg=BG_CARD, fg=TEXT_DIM,
                  relief="flat", cursor="hand2", font=("Segoe UI", 9),
                  command=self._clear_results, padx=10, pady=4).pack(side="left", pady=4)

    # ── Target Management ──────────────────────────────────────────────────────
    def _add_folder(self):
        path = filedialog.askdirectory(title="Select a folder to scan")
        if path:
            self._add_target(path)

    def _add_file(self):
        paths = filedialog.askopenfilenames(
            title="Select Python files to scan",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        for p in paths:
            self._add_target(p)

    def _add_target(self, path: str):
        existing = list(self._target_listbox.get(0, "end"))
        if path not in existing:
            self._target_listbox.insert("end", path)
            self._scan_paths = list(self._target_listbox.get(0, "end"))

    def _remove_selected_target(self, _event=None):
        sel = self._target_listbox.curselection()
        if sel:
            self._target_listbox.delete(sel[0])
            self._scan_paths = list(self._target_listbox.get(0, "end"))

    def _clear_targets(self):
        self._target_listbox.delete(0, "end")
        self._scan_paths = []

    # ── Rule Toggle ────────────────────────────────────────────────────────────
    def _set_all_rules(self, state: bool):
        for var in self._rule_vars.values():
            var.set(state)

    # ── Scanning ───────────────────────────────────────────────────────────────
    def _start_scan(self):
        paths = list(self._target_listbox.get(0, "end"))
        if not paths:
            messagebox.showwarning("No Targets",
                                   "Add at least one folder or file before scanning.")
            return

        enabled_ids = {rid for rid, var in self._rule_vars.items() if var.get()}

        self._scan_btn.configure(state="disabled", text="⏳  Scanning…")
        self._progress.start(12)
        self._status_lbl.configure(text="Scanning…")
        self._clear_results()

        def _worker():
            scanner = Scanner(enabled_rule_ids=enabled_ids)
            result  = scanner.scan(paths, progress_cb=self._on_progress)
            self.root.after(0, lambda: self._on_scan_done(result, paths))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_progress(self, current_file: str, idx: int, total: int):
        name = Path(current_file).name
        self.root.after(0, lambda n=name, i=idx, t=total:
                         self._status_lbl.configure(
                             text=f"Scanning ({i}/{t}): {n}"))

    def _on_scan_done(self, result: ScanResult, paths: list[str]):
        self._scan_result = result
        self._progress.stop()
        self._scan_btn.configure(state="normal", text="▶  SCAN")
        self._ai_btn.configure(state="normal")

        self.history.save(paths, result)
        self._all_findings = list(result.findings) + self._ai_findings
        self._populate_tree(self._all_findings)
        counts = dict(result.counts)
        counts["LOGIC"] = len(self._ai_findings)
        self._update_counters(counts)

        dur   = f"{result.duration:.1f}s"
        files = result.files_scanned
        lines = f"{result.lines_scanned:,}"
        total = len(self._all_findings)
        self._status_lbl.configure(
            text=f"Done in {dur}  ·  {files} files  ·  {lines} lines  ·  {total} findings")
        self._refresh_trend()

    # ── AI Audit ───────────────────────────────────────────────────────────────
    def _start_ai_audit(self):
        paths = list(self._target_listbox.get(0, "end"))
        if not paths:
            messagebox.showwarning("No Targets",
                                   "Add at least one folder or file before generating a prompt.")
            return

        from engine.scanner import collect_python_files
        file_paths = collect_python_files(paths)
        if not file_paths:
            messagebox.showwarning("No Files", "No Python files found in the selected targets.")
            return

        prompt = generate_ai_prompt(file_paths)
        if not prompt:
            messagebox.showerror("Error", "Could not read the selected files.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        
        n = len(file_paths)
        messagebox.showinfo(
            "Prompt Copied!", 
            f"AI Prompt for {n} file(s) copied to clipboard!\n\n"
            "Paste this directly into ChatGPT (GPT-4o), Claude 3.5 Sonnet, or Gemini 1.5 Pro to get a deep logical audit."
        )

    def _populate_tree(self, findings: list[Finding]):
        self._tree.delete(*self._tree.get_children())
        filt = self._filter_var.get()
        filtered = [f for f in findings if filt == "ALL" or f.level == filt]
        self._iid_to_finding: dict[str, Finding] = {}
        for f in filtered:
            fname = Path(f.file).name
            tag   = LVL_TAG.get(f.level, "")
            iid   = self._tree.insert("", "end",
                                       values=(f.level, fname, f.line,
                                               f.title[:100]),
                                       tags=(tag,))
            self._iid_to_finding[iid] = f

    def _update_counters(self, counts: dict[str, int]):
        for lvl, lbl in self._counter_labels.items():
            n = counts.get(lvl, 0)
            lbl.configure(text=f"{lvl}\n{n}")

    def _apply_filter(self):
        if self._all_findings:
            self._populate_tree(self._all_findings)

    def _sort_col(self, col: str):
        """Sort treeview by column."""
        if not self._scan_result:
            return
        items = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children()]
        items.sort()
        for idx, (_, iid) in enumerate(items):
            self._tree.move(iid, "", idx)

    # ── Detail Panel ───────────────────────────────────────────────────────────
    def _on_row_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        finding = self._iid_to_finding.get(iid)
        if not finding:
            return
        self._show_detail(finding)

    def _show_detail(self, f: Finding):
        self._current_finding = f

        lvl_tag = {
            "CRITICAL":  "crit_h",
            "WARNING":   "warn_h",
            "POTENTIAL": "pot_h",
            "INFO":      "info_h",
            "LOGIC":     "logic_h",
        }.get(f.level, "body")

        title = f"[{f.level}]  {f.title}  —  {Path(f.file).name}:{f.line}"
        self._detail_title.configure(text=title)

        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")

        def write(label, content, content_tag="body"):
            self._detail_text.insert("end", f"  {label:<12}", "label")
            self._detail_text.insert("end", f"{content}\n", content_tag)

        write("Rule ID:",  f.rule_id)
        write("File:",     f"{f.file}:{f.line}")
        self._detail_text.insert("end", "\n")
        write("Detail:",   f.detail)
        self._detail_text.insert("end", "\n")
        write("Risk:",     f.risk, "risk")
        self._detail_text.insert("end", "\n")
        write("Fix:",      f.fix, "fix")

        self._detail_text.configure(state="disabled")

    # ── Editor Integration ─────────────────────────────────────────────────────
    def _open_in_editor(self, _event=None):
        finding = getattr(self, "_current_finding", None)
        if not finding:
            sel = self._tree.selection()
            if sel:
                finding = self._iid_to_finding.get(sel[0])
        if not finding:
            return

        fpath = str(Path(finding.file).resolve())
        line  = finding.line if isinstance(finding.line, int) else 1
        editor = self.settings["editor"]

        try:
            if editor == "vscode":
                subprocess.Popen(["code", "--goto", f"{fpath}:{line}"],
                                  shell=True)
            elif editor == "system":
                os.startfile(fpath)
            elif editor == "custom":
                cmd = self.settings["custom_editor_cmd"]
                if not cmd:
                    messagebox.showwarning("No Command",
                                           "Set a custom editor command in Settings first.")
                    return
                cmd = cmd.replace("{file}", fpath).replace("{line}", str(line))
                subprocess.Popen(cmd, shell=True)
        except Exception as e:
            messagebox.showerror("Editor Error", str(e))

    # ── Copy / Export ──────────────────────────────────────────────────────────
    def _copy_finding(self):
        finding = getattr(self, "_current_finding", None)
        if not finding:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(finding.ai_ready_text())
        self._copy_btn.configure(text="✓ Copied!")
        self.root.after(1500, lambda: self._copy_btn.configure(text="📋 Copy for AI"))

    def _copy_all(self):
        if not self._scan_result:
            return
        text = self._build_report_text()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Copied", "All findings copied to clipboard.")

    def _save_report(self):
        if not self._scan_result:
            messagebox.showwarning("No Results", "Run a scan first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if path:
            Path(path).write_text(self._build_report_text(), encoding="utf-8")
            messagebox.showinfo("Saved", f"Report saved to:\n{path}")

    def _build_report_text(self) -> str:
        if not self._scan_result:
            return ""
        r = self._scan_result
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "=" * 72,
            "  PyAuditor — Universal Python Code Audit Report",
            "=" * 72,
            f"  Date    : {now}",
            f"  Files   : {r.files_scanned}",
            f"  Lines   : {r.lines_scanned:,}",
            f"  Duration: {r.duration:.2f}s",
            f"  Paths   : {', '.join(self._scan_paths)}",
            "",
        ]
        for lvl in ["CRITICAL", "WARNING", "POTENTIAL", "INFO"]:
            bucket = [f for f in r.findings if f.level == lvl]
            if not bucket:
                continue
            lines.append("─" * 72)
            lines.append(f"  {lvl}  ({len(bucket)} findings)")
            lines.append("─" * 72)
            for i, f in enumerate(bucket, 1):
                lines.append(f"\n[{lvl} #{i}]  {f.title}")
                lines.append(f"  File   : {f.file}:{f.line}")
                lines.append(f"  Rule   : {f.rule_id}")
                lines.append(f"  Detail : {f.detail}")
                lines.append(f"  Risk   : {f.risk}")
                lines.append(f"  Fix    : {f.fix}")
            lines.append("")

        # Summary table
        lines += [
            "=" * 72,
            "  SUMMARY",
            "=" * 72,
        ]
        for lvl in ["CRITICAL", "WARNING", "POTENTIAL", "INFO"]:
            n = r.counts.get(lvl, 0)
            lines.append(f"  {lvl:<12} {n}")
        lines.append("=" * 72)
        return "\n".join(lines)

    # ── Clear Results ──────────────────────────────────────────────────────────
    def _clear_results(self):
        self._tree.delete(*self._tree.get_children())
        self._iid_to_finding = {}
        self._scan_result = None
        self._current_finding = None
        self._detail_title.configure(text="Select a finding to see details")
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.configure(state="disabled")
        for lvl, lbl in self._counter_labels.items():
            lbl.configure(text=f"{lvl}\n0")

    # ── Settings ───────────────────────────────────────────────────────────────
    def _open_settings(self):
        SettingsDialog(self.root, self.settings)

    def _open_info(self):
        InfoDialog(self.root)

    # ── Trend ──────────────────────────────────────────────────────────────────
    def _refresh_trend(self):
        trend = self.history.trend_text()
        self._trend_lbl.configure(text=trend)

    # ── Run ───────────────────────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    PyAuditorApp().run()
