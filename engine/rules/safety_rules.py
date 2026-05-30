"""Safety rules: exception handling, os._exit, mutable defaults, bare except, shadow builtins."""
import ast
import re
from engine.rules.base import Rule
from engine.finding import Finding


class BareExceptRule(Rule):
    rule_id  = "bare_except"
    category = "Safety"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                results.append(self._make(
                    "WARNING", path, node.lineno,
                    "Bare `except:` Catches Everything Including SystemExit",
                    "An `except:` clause with no exception type catches *all* exceptions, "
                    "including `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`. "
                    "This prevents the program from being cleanly stopped.",
                    "The program may become impossible to stop with Ctrl+C or a shutdown signal. "
                    "Critical system exceptions are silently swallowed, masking serious failures.",
                    "Replace `except:` with `except Exception:` to allow system exits through, "
                    "or be even more specific: `except (ValueError, OSError):` etc."
                ))
        return results


class ExceptPassRule(Rule):
    rule_id  = "except_pass"
    category = "Safety"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    results.append(self._make(
                        "WARNING", path, node.lineno,
                        "Silent Exception Swallowing — `except: pass`",
                        f"The exception handler at line {node.lineno} catches an exception "
                        "and does absolutely nothing with it — not even a log message.",
                        "If a file read, API call, or DB operation fails here, the system "
                        "silently continues with incorrect or missing data. During debugging, "
                        "there is zero trace left — you will spend hours finding why something "
                        "stopped working with no error in sight.",
                        "Replace `pass` with at least: "
                        "`logger.warning(f'Suppressed error in {__name__}: {e}')`. "
                        "If recovery is impossible, re-raise with `raise`."
                    ))
        return results


class MutableDefaultArgRule(Rule):
    rule_id  = "mutable_default_arg"
    category = "Safety"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for default in node.args.defaults + node.args.kw_defaults:
                if default is None:
                    continue
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    type_name = type(default).__name__.replace("ast.", "")
                    results.append(self._make(
                        "WARNING", path, node.lineno,
                        f"Mutable Default Argument (`{type_name}`) in `{node.name}()`",
                        f"`{node.name}()` uses a mutable `{type_name}` as a default argument value. "
                        "Python creates this object *once* at function definition time and reuses it "
                        "across all calls that don't provide that argument.",
                        "All callers that omit this argument share the *same* list/dict/set object. "
                        "Mutating it in one call mutates it for every future call — classic hidden "
                        "state bug that is extremely hard to debug.",
                        f"Change the default to `None` and initialise inside the function body:\n"
                        f"  `def {node.name}(..., param=None):`\n"
                        f"  `    if param is None: param = []  # or {{}} or set()`"
                    ))
        return results


class ShadowBuiltinRule(Rule):
    rule_id  = "shadow_builtin"
    category = "Safety"
    BUILTINS = frozenset([
        "list", "dict", "set", "tuple", "str", "int", "float", "bool",
        "bytes", "type", "object", "range", "map", "filter", "zip",
        "input", "print", "open", "len", "sum", "min", "max", "id",
        "hash", "sorted", "reversed", "enumerate", "vars", "dir",
    ])

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in self.BUILTINS:
                        results.append(self._make(
                            "WARNING", path, node.lineno,
                            f"Built-in Name `{target.id}` Shadowed by Local Variable",
                            f"A local variable named `{target.id}` is assigned at line {node.lineno}. "
                            f"This shadows Python's built-in `{target.id}` for the rest of this scope.",
                            f"Any code after this line that tries to use the real built-in `{target.id}` "
                            "will instead get the local variable, causing `TypeError` or wrong results. "
                            "This is especially dangerous in long functions where the shadowing is far "
                            "from the affected code.",
                            f"Rename the variable to something descriptive that doesn't conflict: "
                            f"e.g. `{target.id}_items`, `{target.id}_data`, `my_{target.id}`."
                        ))
        return results


class OsExitRule(Rule):
    rule_id  = "os_exit_bypass"
    category = "Safety"

    def check(self, path, lines, tree) -> list[Finding]:
        results = []
        for lineno, line in enumerate(lines, 1):
            if "os._exit(" in line and not line.strip().startswith("#"):
                results.append(self._make(
                    "WARNING", path, lineno,
                    "os._exit() Bypasses All Python Cleanup",
                    "`os._exit()` terminates the process immediately at the OS level, "
                    "bypassing all Python finalizers: `finally` blocks, `atexit` handlers, "
                    "`__del__` methods, and context managers.",
                    "Open file handles may not be flushed. Database connections are not "
                    "gracefully closed. In-flight async tasks are abandoned mid-operation. "
                    "This can cause data corruption, partial writes, or locked files on disk.",
                    "Replace `os._exit(0)` with a coordinated shutdown: "
                    "1) Call your engine's `shutdown()` or `stop()` method. "
                    "2) Then use `sys.exit(0)` or `root.destroy()` for GUI apps."
                ))
        return results


class CircularImportRule(Rule):
    rule_id  = "circular_import"
    category = "Safety"

    def check(self, path, lines, tree) -> list[Finding]:
        # This is handled at the scanner level across files; single-file stub only
        return []
