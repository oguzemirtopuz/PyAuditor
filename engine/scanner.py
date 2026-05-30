"""Scanner: discovers Python files, parses AST, runs all enabled rules."""
import ast
import os
import time
from pathlib import Path
from typing import Callable

from engine.finding import Finding
from engine.rules import ALL_RULES


def _read(path: str) -> tuple[str | None, list[str]]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return text, text.splitlines()
    except Exception:
        return None, []


def _parse(text: str) -> ast.Module | None:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def collect_python_files(paths: list[str]) -> list[str]:
    """Given a list of files/directories, return all .py file paths."""
    result = []
    for p in paths:
        p = Path(p)
        if p.is_file() and p.suffix == ".py":
            result.append(str(p))
        elif p.is_dir():
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith(".py"):
                        result.append(str(Path(root) / f))
    return sorted(set(result))


class ScanResult:
    def __init__(self):
        self.findings: list[Finding] = []
        self.files_scanned: int = 0
        self.lines_scanned: int = 0
        self.duration: float = 0.0
        self.errors: list[str] = []

    @property
    def by_level(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.level, []).append(f)
        return out

    @property
    def counts(self) -> dict[str, int]:
        c = {"CRITICAL": 0, "WARNING": 0, "POTENTIAL": 0, "INFO": 0}
        for f in self.findings:
            c[f.level] = c.get(f.level, 0) + 1
        return c


class Scanner:
    def __init__(self, enabled_rule_ids: set[str] | None = None):
        """
        enabled_rule_ids: set of rule_id strings to run.
                          If None, all rules are enabled.
        """
        self.enabled_ids = enabled_rule_ids

    def scan(self,
             paths: list[str],
             progress_cb: Callable[[str, int, int], None] | None = None
             ) -> ScanResult:
        """
        Scan all Python files in `paths`.
        progress_cb(current_file, current_index, total) called for each file.
        """
        result = ScanResult()
        files = collect_python_files(paths)
        total = len(files)
        t0 = time.perf_counter()

        rules = [r for r in ALL_RULES
                 if (self.enabled_ids is None or r.rule_id in self.enabled_ids)
                 and r.enabled]

        for idx, fpath in enumerate(files):
            if progress_cb:
                progress_cb(fpath, idx + 1, total)

            text, lines = _read(fpath)
            if text is None:
                result.errors.append(f"Could not read: {fpath}")
                continue

            result.files_scanned += 1
            result.lines_scanned += len(lines)

            # Syntax check first
            tree = _parse(text)
            if tree is None:
                try:
                    ast.parse(text)
                except SyntaxError as e:
                    result.findings.append(Finding(
                        level="CRITICAL",
                        rule_id="syntax_error",
                        file=fpath,
                        line=e.lineno or "?",
                        title="Syntax Error — File Cannot Be Parsed",
                        detail=f"Python cannot parse this file: {e.msg}",
                        risk="This file is completely broken — Python cannot import or run it. "
                             "Everything that depends on this module will fail with ImportError.",
                        fix=f"Fix the syntax error near line {e.lineno}: {e.msg}",
                        category="Safety",
                    ))

            for rule in rules:
                try:
                    findings = rule.check(fpath, lines, tree)
                    result.findings.extend(findings)
                except Exception as ex:
                    result.errors.append(f"Rule {rule.rule_id} crashed on {fpath}: {ex}")

        result.findings.sort(key=lambda f: (f.order, f.file, str(f.line)))
        result.duration = time.perf_counter() - t0
        return result
