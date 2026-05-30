from dataclasses import dataclass, field
from typing import Optional


LEVEL_ORDER = {"CRITICAL": 0, "WARNING": 1, "POTENTIAL": 2, "INFO": 3, "LOGIC": 0}
LEVEL_COLORS = {
    "CRITICAL":  "#FF4C4C",
    "WARNING":   "#FFB347",
    "POTENTIAL": "#FF8C00",
    "INFO":      "#5BC0EB",
    "LOGIC":     "#BF5AF2",
}
LEVEL_BG = {
    "CRITICAL":  "#3A0A0A",
    "WARNING":   "#2E1F00",
    "POTENTIAL": "#1E1000",
    "INFO":      "#001A2E",
    "LOGIC":     "#1A0A2E",
}


@dataclass
class Finding:
    """Represents a single audit finding."""
    level:    str          # CRITICAL / WARNING / POTENTIAL / INFO
    rule_id:  str          # e.g. "asyncio_lock_race"
    file:     str          # relative or absolute path
    line:     int | str    # line number or "N/A"
    title:    str          # short one-liner
    detail:   str          # full technical explanation
    risk:     str          # "if not fixed, this can happen..."
    fix:      str          # exact actionable fix instruction
    category: str = ""     # Async / Safety / DeadCode / Design / Potential / Info

    @property
    def order(self) -> int:
        return LEVEL_ORDER.get(self.level, 99)

    @property
    def color(self) -> str:
        return LEVEL_COLORS.get(self.level, "#AAAAAA")

    @property
    def bg_color(self) -> str:
        return LEVEL_BG.get(self.level, "#111111")

    def ai_ready_text(self) -> str:
        """Returns a copy-paste ready block for AI assistants."""
        return (
            f"[{self.level}] {self.title}\n"
            f"File   : {self.file}:{self.line}\n"
            f"Rule   : {self.rule_id}\n"
            f"Detail : {self.detail}\n"
            f"Risk   : {self.risk}\n"
            f"Fix    : {self.fix}\n"
        )
