"""Potential / future risk rules: magic numbers, TODO/FIXME, hardcoded paths,
print statements, multiword stopwords, stale log values, broad exception catch."""
import ast
import re
from engine.rules.base import Rule
from engine.finding import Finding


class MagicNumberRule(Rule):
    rule_id   = "magic_number"
    category  = "Potential"
    # Numbers always acceptable without explanation
    ALLOWED   = frozenset([0, 1, -1, 2, 10, 100, 1000])
    # Only flag numbers used in comparisons or assignments — not every AST literal
    PARENT_OK = (ast.Compare, ast.Assign, ast.AugAssign, ast.AnnAssign,
                 ast.keyword, ast.Return)

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        seen_lines: set[int] = set()

        # Build parent map
        parent: dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[id(child)] = node

        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if not isinstance(node.value, (int, float)):
                continue
            if node.value in self.ALLOWED:
                continue
            if node.lineno in seen_lines:
                continue
            p = parent.get(id(node))
            if not isinstance(p, self.PARENT_OK):
                continue
            # Skip inside function default args and annotations
            gp = parent.get(id(p))
            if isinstance(gp, (ast.FunctionDef, ast.AsyncFunctionDef, ast.arguments)):
                continue
            seen_lines.add(node.lineno)
            results.append(self._make(
                "POTENTIAL", path, node.lineno,
                f"Magic Number `{node.value}` — Consider a Named Constant",
                f"The numeric literal `{node.value}` is used at line {node.lineno} "
                "without a descriptive name explaining what it represents.",
                "If this value ever needs to change, you must find every occurrence "
                "manually. Readers have no context for what the number means — is 900 "
                "seconds? pixels? a limit? a threshold?",
                f"Define at module level: `TIMEOUT_SECONDS = {node.value}` (use a "
                "descriptive name), then replace `{node.value}` with the constant name."
            ))
        return results


class TodoFixmeRule(Rule):
    rule_id  = "todo_fixme"
    category = "Potential"
    PATTERN  = re.compile(r'#\s*(TODO|FIXME|HACK|XXX|BUG|TEMP)\b', re.IGNORECASE)

    def check(self, path, lines, tree) -> list[Finding]:
        results = []
        for lineno, line in enumerate(lines, 1):
            m = self.PATTERN.search(line)
            if m:
                tag = m.group(1).upper()
                comment = line.strip().lstrip("#").strip()
                results.append(self._make(
                    "POTENTIAL", path, lineno,
                    f"{tag} Comment — Incomplete or Deferred Code",
                    f"Line {lineno} contains a `{tag}` marker: `{comment[:80]}`",
                    f"{'FIXME/BUG markers indicate known broken code' if tag in ('FIXME','BUG') else 'TODO/HACK markers indicate deferred or temporary code'}. "
                    "If this is never addressed, it becomes permanent technical debt. "
                    f"{'Known broken code in production causes silent failures.' if tag in ('FIXME','BUG') else 'Hacks tend to rot and break when surrounding code changes.'}",
                    f"Address the `{tag}` at line {lineno}, then remove the marker. "
                    "If deferring intentionally, create a tracked issue and reference it: "
                    f"`# TODO(#123): description`"
                ))
        return results


class HardcodedPathRule(Rule):
    rule_id = "hardcoded_path"
    category = "Potential"
    PATTERN = re.compile(
        r"""['"]([A-Za-z]:\\[^'"]+|/home/[^'"]+|/Users/[^'"]+|/root/[^'"]+)['"]"""
    )

    def check(self, path, lines, tree) -> list[Finding]:
        results = []
        for lineno, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            m = self.PATTERN.search(line)
            if m:
                found = m.group(1)
                results.append(self._make(
                    "POTENTIAL", path, lineno,
                    f"Hardcoded Filesystem Path `{found[:50]}`",
                    f"Line {lineno} contains a hardcoded absolute path: `{found}`. "
                    "This path only exists on your machine.",
                    "On any other machine, CI/CD environment, or Docker container "
                    "this path does not exist — the application crashes or silently "
                    "fails to find the file. Collaboration and deployment become impossible.",
                    "Replace with a relative path, an environment variable "
                    "(`os.environ.get('MY_PATH', 'default')`), or `pathlib.Path(__file__).parent`."
                ))
        return results


class PrintStatementRule(Rule):
    rule_id  = "print_statement"
    category = "Potential"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Expr) and
                    isinstance(node.value, ast.Call) and
                    isinstance(node.value.func, ast.Name) and
                    node.value.func.id == "print"):
                results.append(self._make(
                    "POTENTIAL", path, node.lineno,
                    f"`print()` Statement in Production Code",
                    f"`print()` call at line {node.lineno}. "
                    "Raw print statements bypass the logging framework.",
                    "Print output goes to stdout with no timestamp, no log level, no file, "
                    "and no way to filter or redirect it. In production or background "
                    "services, this output is lost. You cannot enable/disable it at runtime.",
                    "Replace with `logger.debug(...)` or `logger.info(...)` from the `logging` module. "
                    "Use `logging.getLogger(__name__)` at the top of the file."
                ))
        return results


class BroadExceptionCatchRule(Rule):
    rule_id  = "broad_exception_catch"
    category = "Potential"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.ExceptHandler) and
                    node.type is not None and
                    isinstance(node.type, ast.Name) and
                    node.type.id == "Exception"):
                # Only flag if the body is NOT re-raising
                has_raise = any(isinstance(s, ast.Raise) for s in ast.walk(node))
                if not has_raise:
                    results.append(self._make(
                        "POTENTIAL", path, node.lineno,
                        "Overly Broad `except Exception` Catch",
                        f"`except Exception` at line {node.lineno} catches every possible error "
                        "without discriminating between expected and unexpected failures.",
                        "You may be silently swallowing unexpected errors (e.g. `MemoryError`, "
                        "`AttributeError`, `KeyError`) that indicate real bugs. This makes "
                        "debugging extremely difficult — the real error is hidden behind generic handling.",
                        "Narrow the exception type to exactly what you expect: "
                        "`except (ValueError, OSError):` instead of `except Exception:`. "
                        "Let unexpected exceptions propagate naturally."
                    ))
        return results


class MultiwordStopwordRule(Rule):
    rule_id  = "multiword_stopword"
    category = "Potential"
    STOP_PAT = re.compile(r'stop_?words\s*=\s*[\{\[]', re.IGNORECASE)

    def check(self, path, lines, tree) -> list[Finding]:
        results = []
        in_block = False
        depth = 0
        for lineno, line in enumerate(lines, 1):
            if self.STOP_PAT.search(line):
                in_block = True
                depth = line.count("{") + line.count("[") - line.count("}") - line.count("]")
                if depth <= 0:
                    in_block = False
                continue
            if in_block:
                depth += line.count("{") + line.count("[") - line.count("}") - line.count("]")
                for s in re.findall(r"'([^']*)'", line) + re.findall(r'"([^"]*)"', line):
                    if " " in s.strip():
                        results.append(self._make(
                            "POTENTIAL", path, lineno,
                            f"Multi-Word Stop Word `'{s}'` Never Matches Tokenizer",
                            f"Stop words set contains `'{s}'` which has spaces. "
                            "Word-level tokenizers split text into individual tokens — "
                            "a multi-word string can never match a single token.",
                            "This stop word is completely non-functional dead code. "
                            "Words inside it are never filtered, letting noise through "
                            "your NLP pipeline silently.",
                            f"Split `'{s}'` into individual words: "
                            + ", ".join(f"'{w}'" for w in s.split()) +
                            " and add each separately to the stop words set."
                        ))
                if depth <= 0:
                    in_block = False
        return results


class StaleLogValueRule(Rule):
    rule_id  = "stale_log_value"
    category = "Potential"
    PATTERN  = re.compile(r'(logger\.|logging\.|print\s*\().*Threshold\s+([\d.]+)', re.IGNORECASE)

    def check(self, path, lines, tree) -> list[Finding]:
        results = []
        # Collect all float literals in the file
        all_floats: set[float] = set()
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, float):
                    all_floats.add(node.value)

        for lineno, line in enumerate(lines, 1):
            m = self.PATTERN.search(line)
            if m:
                stated = float(m.group(2))
                if stated not in all_floats and all_floats:
                    results.append(self._make(
                        "POTENTIAL", path, lineno,
                        f"Stale Threshold Value `{stated}` in Log Message",
                        f"The log message at line {lineno} references threshold `{stated}`, "
                        f"but this exact value does not appear as a constant in the file. "
                        f"Actual float constants found: {sorted(all_floats)}",
                        "The log message is lying. During debugging, you will read the log, "
                        "see `{stated}` and look for that value in the code — and find "
                        "something different. This wastes debugging time and erodes trust in logs.",
                        f"Update the log message at line {lineno} to reflect the actual "
                        f"threshold value currently used in the code."
                    ))
        return results
