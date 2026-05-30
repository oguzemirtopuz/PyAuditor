"""Design quality rules: long functions, deep nesting, missing type hints, missing docstrings, long lines."""
import ast
import re
from engine.rules.base import Rule
from engine.finding import Finding


class LongFunctionRule(Rule):
    rule_id   = "long_function"
    category  = "Design"
    THRESHOLD = 80

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            length = node.end_lineno - node.lineno + 1
            if length > self.THRESHOLD:
                results.append(self._make(
                    "POTENTIAL", path, node.lineno,
                    f"Long Function `{node.name}()` — {length} Lines",
                    f"`{node.name}` spans {length} lines (threshold: {self.THRESHOLD}). "
                    "Functions this long typically do more than one thing.",
                    "Long functions are hard to test, hard to read, and hide bugs. "
                    "When one part breaks, it's hard to isolate. Future changes risk "
                    "unintended side effects in unrelated code paths inside the same function.",
                    f"Refactor `{node.name}()` by extracting logical sub-sections into "
                    "smaller, named helper functions. Aim for each function to do exactly one thing."
                ))
        return results


class DeepNestingRule(Rule):
    rule_id   = "deep_nesting"
    category  = "Design"
    THRESHOLD = 4

    def _max_depth(self, node, current=0):
        """Recursively compute max nesting depth of if/for/while/with."""
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.AsyncWith, ast.AsyncFor)):
            current += 1
        max_d = current
        for child in ast.iter_child_nodes(node):
            max_d = max(max_d, self._max_depth(child, current))
        return max_d

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            depth = self._max_depth(node)
            if depth >= self.THRESHOLD:
                results.append(self._make(
                    "POTENTIAL", path, node.lineno,
                    f"Deep Nesting ({depth} Levels) in `{node.name}()`",
                    f"`{node.name}()` has {depth} levels of nested `if`/`for`/`while`/`with` blocks "
                    f"(threshold: {self.THRESHOLD}).",
                    "Deeply nested code is a breeding ground for off-by-one errors, "
                    "missed edge cases, and logic bugs. Each added nesting level multiplies "
                    "the number of code paths to mentally track and test.",
                    f"Reduce nesting in `{node.name}()` via: early returns/guard clauses, "
                    "extracting inner blocks into helper functions, or using `continue`/`break`."
                ))
        return results


class MissingTypeHintRule(Rule):
    rule_id  = "missing_type_hint"
    category = "Design"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue  # Skip private/dunder
            missing = []
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    missing.append(arg.arg)
            has_return = node.returns is not None
            if missing or not has_return:
                parts = []
                if missing:
                    parts.append(f"parameters without type hints: {missing}")
                if not has_return:
                    parts.append("missing return type annotation")
                results.append(self._make(
                    "INFO", path, node.lineno,
                    f"Missing Type Hints in Public Function `{node.name}()`",
                    f"`{node.name}()` has {', '.join(parts)}.",
                    "Without type hints, IDEs and static analysis tools cannot catch "
                    "type mismatches at development time. Callers have no contract to "
                    "follow. Bugs from wrong argument types only appear at runtime.",
                    f"Add type hints to `{node.name}()`: e.g. "
                    f"`def {node.name}(param: str, count: int) -> bool:`"
                ))
        return results


class MissingDocstringRule(Rule):
    rule_id  = "missing_docstring"
    category = "Design"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name.startswith("_"):
                continue
            if not (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                results.append(self._make(
                    "INFO", path, node.lineno,
                    f"Missing Docstring on Public {kind.title()} `{node.name}`",
                    f"The public {kind} `{node.name}` has no docstring.",
                    "Future contributors (including yourself in 6 months) have no explanation "
                    "of what this does, what arguments it expects, or what it returns. "
                    "Auto-generated documentation will be empty.",
                    f'Add a docstring: `"""{node.name} does X given Y, returns Z."""`'
                ))
        return results


class LongLineRule(Rule):
    rule_id   = "long_line"
    category  = "Design"
    THRESHOLD = 120

    def check(self, path, lines, tree) -> list[Finding]:
        results = []
        for lineno, line in enumerate(lines, 1):
            if len(line.rstrip()) > self.THRESHOLD:
                results.append(self._make(
                    "INFO", path, lineno,
                    f"Line Too Long ({len(line.rstrip())} chars)",
                    f"Line {lineno} is {len(line.rstrip())} characters long (threshold: {self.THRESHOLD}).",
                    "Very long lines are hard to read without horizontal scrolling and "
                    "are often a sign that a complex expression should be broken up or "
                    "a variable extracted for clarity.",
                    "Break the line using parentheses for implicit continuation, or "
                    "extract a sub-expression into a named variable."
                ))
        return results
