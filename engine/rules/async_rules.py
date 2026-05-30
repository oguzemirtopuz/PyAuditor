"""Async / concurrency rules."""
import ast
import re
from engine.rules.base import Rule
from engine.finding import Finding


class AsyncioLockRaceRule(Rule):
    rule_id  = "asyncio_lock_race"
    category = "Async"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            init_has_none = False
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    for stmt in ast.walk(item):
                        if (isinstance(stmt, ast.Assign) and
                                any(isinstance(t, ast.Attribute) and "_lock" in t.attr
                                    for t in stmt.targets)):
                            if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                                init_has_none = True
            if not init_has_none:
                continue
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    src = "\n".join(lines[item.lineno - 1: item.end_lineno])
                    if "self._lock is None" in src and "asyncio.Lock()" in src:
                        results.append(self._make(
                            "CRITICAL", path, item.lineno,
                            f"asyncio.Lock Lazy-Init Race Condition in `{node.name}`",
                            f"`{node.name}.__init__` sets `self._lock = None`, then `{item.name}()` "
                            f"creates it lazily with `if self._lock is None: self._lock = asyncio.Lock()`. "
                            f"Two coroutines calling `{item.name}()` simultaneously will both see `None` "
                            f"and each create a separate Lock — mutual exclusion breaks entirely.",
                            "Two concurrent tasks will run simultaneously inside a block that should be "
                            "exclusive. This causes data corruption, double-writes, or torn reads in the "
                            "shared state (e.g. conversation history, memory DB).",
                            f"In `{node.name}.__init__`, replace `self._lock = None` with "
                            f"`self._lock = asyncio.Lock()`. Then delete the "
                            f"`if self._lock is None` block inside `{item.name}()`."
                        ))
        return results


class BlockingInAsyncRule(Rule):
    rule_id  = "blocking_in_async"
    category = "Async"
    BLOCKING = [
        ("locale.setlocale",         "Freezes the event loop while changing locale — all other coroutines stall."),
        ("time.sleep(",              "Synchronous sleep blocks the entire event loop thread."),
        ("requests.get(",            "`requests` is a synchronous HTTP library — blocks all async tasks."),
        ("requests.post(",           "`requests` is a synchronous HTTP library — blocks all async tasks."),
        ("urllib.request.urlopen(",  "Synchronous URL fetch — blocks the event loop."),
        ("subprocess.run(",          "Synchronous subprocess — blocks the event loop."),
        ("subprocess.call(",         "Synchronous subprocess — blocks the event loop."),
        ("open(",                    "Synchronous file I/O inside async function — consider `aiofiles`."),
    ]

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            body_lines = lines[node.lineno - 1: node.end_lineno]
            for rel_i, line in enumerate(body_lines, node.lineno):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for call, why in self.BLOCKING:
                    if call in stripped:
                        results.append(self._make(
                            "CRITICAL", path, rel_i,
                            f"Blocking Call `{call.rstrip('(')}()` Inside `async def {node.name}()`",
                            f"`{call.rstrip('(')}` is a synchronous (blocking) call used directly inside "
                            f"an `async def` function. {why}",
                            "The entire asyncio event loop freezes for the duration of this call. All "
                            "other coroutines (voice input, GUI updates, watchdog timers) are frozen too. "
                            "On slow machines or network calls this can cause seconds-long hangs.",
                            f"Move `{call.rstrip('(')}(...)` out of `{node.name}()` into `__init__`, OR "
                            f"wrap it: `await asyncio.get_running_loop().run_in_executor(None, lambda: {call.rstrip('(')}(...))`."
                        ))
        return results


class MissingAwaitRule(Rule):
    rule_id  = "missing_await"
    category = "Async"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        # Collect all async function names defined in this file
        async_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                async_names.add(node.name)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for stmt in ast.walk(node):
                # A bare Expr containing a Call to a known async function — not awaited
                if (isinstance(stmt, ast.Expr) and
                        isinstance(stmt.value, ast.Call)):
                    call = stmt.value
                    fname = None
                    if isinstance(call.func, ast.Name):
                        fname = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        fname = call.func.attr
                    if fname and fname in async_names:
                        results.append(self._make(
                            "CRITICAL", path, stmt.lineno,
                            f"Possibly Missing `await` on Coroutine `{fname}()`",
                            f"`{fname}()` is an async function called without `await`. "
                            f"Python creates a Coroutine object but never executes it.",
                            f"`{fname}()` silently does nothing. Any side effects (DB write, "
                            "network call, state update) are skipped without any error or warning.",
                            f"Add `await` before the call: `await {fname}(...)`."
                        ))
        return results
