"""Dead code rules: unused params, unused self attrs, widget not packed, duplicate list items."""
import ast
import re
from engine.rules.base import Rule
from engine.finding import Finding


class DeadParameterRule(Rule):
    rule_id  = "dead_parameter"
    category = "DeadCode"
    SKIP     = frozenset(["self", "cls", "args", "kwargs", "_"])

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [a.arg for a in node.args.args if a.arg not in self.SKIP]
            if not params:
                continue
            body_src = "\n".join(lines[node.lineno: node.end_lineno])
            for param in params:
                if not re.search(r'\b' + re.escape(param) + r'\b', body_src):
                    results.append(self._make(
                        "WARNING", path, node.lineno,
                        f"Dead Parameter `{param}` in `{node.name}()`",
                        f"`{node.name}()` declares parameter `{param}` but never uses it "
                        f"anywhere in the function body.",
                        "Callers passing a value for this parameter believe it affects behavior. "
                        "It silently does nothing — misleading API, wasted argument binding, "
                        "and potential future bugs if someone adds logic expecting it was used.",
                        f"Either: (a) use `{param}` in the function body, or "
                        f"(b) remove it from the signature of `{node.name}()` and update all callers."
                    ))
        return results


class UnusedSelfAttrRule(Rule):
    rule_id  = "unused_self_attr"
    category = "DeadCode"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            class_src = "\n".join(lines[node.lineno - 1: node.end_lineno])
            init_assigns: dict[str, int] = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    for stmt in ast.walk(item):
                        if (isinstance(stmt, ast.Assign) and
                                len(stmt.targets) == 1 and
                                isinstance(stmt.targets[0], ast.Attribute) and
                                isinstance(stmt.targets[0].value, ast.Name) and
                                stmt.targets[0].value.id == "self"):
                            attr = stmt.targets[0].attr
                            if attr.startswith("_"):
                                continue
                            init_assigns[attr] = stmt.lineno

            for attr, lineno in init_assigns.items():
                count = len(re.findall(r'\bself\.' + re.escape(attr) + r'\b', class_src))
                if count <= 1:
                    results.append(self._make(
                        "WARNING", path, lineno,
                        f"Possibly Unused Attribute `self.{attr}` in `{node.name}`",
                        f"`{node.name}.__init__` assigns `self.{attr}` but it appears nowhere "
                        f"else in the class body (only the assignment itself was found).",
                        "Dead object stored in memory for the lifetime of every instance. "
                        "If this was meant to be used and isn't, a feature is silently missing. "
                        "If it's genuinely unused, it wastes memory and confuses readers.",
                        f"If unused: remove `self.{attr} = ...` from `{node.name}.__init__`. "
                        f"If planned for future: add `# TODO: use self.{attr}` comment."
                    ))
        return results


class WidgetNotPackedRule(Rule):
    rule_id  = "widget_not_packed"
    category = "DeadCode"
    CREATE_PAT = re.compile(r'^\s*(\w+)\s*=\s*(tk|ctk|ttk)\.(Scrollbar|Label|Button|Frame|Text|Entry|Canvas)\s*\(')
    PACK_PAT   = re.compile(r'\b(\w+)\.(pack|grid|place)\s*\(')

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            func_lines = lines[node.lineno - 1: node.end_lineno]
            created: dict[str, int] = {}
            packed: set[str] = set()
            for rel_i, line in enumerate(func_lines, node.lineno):
                m = self.CREATE_PAT.match(line)
                if m and m.group(1) != "self":
                    created[m.group(1)] = rel_i
                m2 = self.PACK_PAT.search(line)
                if m2:
                    packed.add(m2.group(1))
            for varname, lineno in created.items():
                if varname not in packed:
                    results.append(self._make(
                        "WARNING", path, lineno,
                        f"Widget `{varname}` Created But Never Laid Out",
                        f"`{varname}` is created as a GUI widget at line {lineno} but "
                        f"`.pack()`, `.grid()`, or `.place()` is never called on it.",
                        "The widget is invisible — it exists in memory but the user never sees it. "
                        "This is almost always a forgotten `.pack()` call, meaning a UI element "
                        "the developer intended to show is silently missing from the interface.",
                        f"Add after line {lineno}: `{varname}.pack(...)` or `{varname}.grid(...)`. "
                        "If the widget is intentionally hidden, add a comment explaining why."
                    ))
        return results


class DuplicateListItemsRule(Rule):
    rule_id  = "duplicate_list_items"
    category = "DeadCode"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.List):
                continue
            values = [str(e.value) for e in node.elts if isinstance(e, ast.Constant)]
            seen, dupes = set(), []
            for v in values:
                if v in seen and v not in dupes:
                    dupes.append(v)
                seen.add(v)
            if dupes:
                results.append(self._make(
                    "WARNING", path, node.lineno,
                    "Duplicate Items in List Literal",
                    f"The list at line {node.lineno} contains duplicate constant values: {dupes}. "
                    "This is almost always a copy-paste mistake.",
                    "If this list is iterated, each duplicate item is processed twice — "
                    "double the work, double the results, double the side effects. "
                    "If it's a config list, duplicate entries cause unexpected behavior.",
                    f"Remove the duplicate entries from the list at line {node.lineno}: {dupes}"
                ))
        return results


class UnusedImportRule(Rule):
    rule_id  = "unused_import"
    category = "DeadCode"

    def check(self, path, lines, tree) -> list[Finding]:
        if tree is None:
            return []
        results = []
        full_src = "\n".join(lines)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split(".")[0]
                    # Count usages beyond the import line itself
                    count = len(re.findall(r'\b' + re.escape(name) + r'\b', full_src))
                    if count <= 1:
                        results.append(self._make(
                            "INFO", path, node.lineno,
                            f"Unused Import `{alias.name}`",
                            f"`import {alias.name}` at line {node.lineno} is never referenced "
                            f"anywhere in this file.",
                            "Dead imports slow down startup time and clutter the namespace. "
                            "They mislead readers into thinking the module is needed.",
                            f"Remove `import {alias.name}` from line {node.lineno}."
                        ))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname if alias.asname else alias.name
                    count = len(re.findall(r'\b' + re.escape(name) + r'\b', full_src))
                    if count <= 1:
                        results.append(self._make(
                            "INFO", path, node.lineno,
                            f"Unused Import `{name}` from `{node.module}`",
                            f"`from {node.module} import {alias.name}` at line {node.lineno} "
                            f"is never used in this file.",
                            "Dead imports slow startup time and mislead readers.",
                            f"Remove `{alias.name}` from the import at line {node.lineno}."
                        ))
        return results
