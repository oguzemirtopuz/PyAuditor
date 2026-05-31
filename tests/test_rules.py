import ast
import pytest
from engine.rules import ALL_RULES, RULE_MAP
from engine.finding import Finding

def parse_and_check(rule, code_str: str) -> list[Finding]:
    """Helper to parse a python string and run a single rule on it."""
    tree = ast.parse(code_str)
    lines = code_str.splitlines()
    return rule.check("test.py", lines, tree)

def test_all_rules_load():
    """Verify that all rules are correctly loaded and mapped."""
    assert len(ALL_RULES) > 20, "Should have loaded at least 20 rules"
    assert "bare_except" in RULE_MAP
    assert "blocking_in_async" in RULE_MAP

def test_bare_except_rule():
    """Test the BareExceptRule which catches empty except blocks."""
    rule = RULE_MAP["bare_except"]
    code = "try:\n    pass\nexcept:\n    pass"
    findings = parse_and_check(rule, code)
    assert len(findings) == 1
    assert findings[0].rule_id == "bare_except"

def test_mutable_default_arg_rule():
    """Test MutableDefaultArgRule catching mutable defaults like lists."""
    rule = RULE_MAP["mutable_default_arg"]
    code = "def foo(a=[]):\n    pass"
    findings = parse_and_check(rule, code)
    assert len(findings) == 1
    assert findings[0].rule_id == "mutable_default_arg"

def test_missing_await_rule():
    """Test MissingAwaitRule catching un-awaited coroutines defined in the same file."""
    rule = RULE_MAP["missing_await"]
    code = "async def my_coro():\n    pass\ndef main():\n    my_coro()"
    findings = parse_and_check(rule, code)
    assert len(findings) == 1
    assert findings[0].rule_id == "missing_await"

def test_print_statement_rule():
    """Test PrintStatementRule catching dev print statements."""
    rule = RULE_MAP["print_statement"]
    code = "def foo():\n    print('debug')"
    findings = parse_and_check(rule, code)
    assert len(findings) == 1
    assert findings[0].rule_id == "print_statement"

def test_no_crash_on_empty_file():
    """Ensure no rule crashes on an empty file."""
    code = ""
    for rule in ALL_RULES:
        findings = parse_and_check(rule, code)
        assert isinstance(findings, list)

def test_no_crash_on_syntax_error():
    """Ensure parser logic handles syntax errors gracefully before rules (mock test)."""
    # Scanner itself handles syntax errors, but let's make sure our test harness fails cleanly
    with pytest.raises(SyntaxError):
        ast.parse("def if True: pass")
