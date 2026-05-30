from abc import ABC, abstractmethod
from engine.finding import Finding


class Rule(ABC):
    """Base class for all audit rules."""

    rule_id:  str = "base"
    category: str = "General"
    enabled:  bool = True

    @abstractmethod
    def check(self, path: str, lines: list[str], tree) -> list[Finding]:
        """Run the check and return a list of findings."""
        ...

    def _make(self, level, path, line, title, detail, risk, fix) -> Finding:
        return Finding(
            level=level,
            rule_id=self.rule_id,
            file=path,
            line=line,
            title=title,
            detail=detail,
            risk=risk,
            fix=fix,
            category=self.category,
        )
