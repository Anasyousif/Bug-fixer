"""
models.py
---------
Shared data structures used across the analyzer, rules, and fixer.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bug:
    """A single detected bug/issue."""
    file: str
    line: int
    col: int
    rule_id: str
    title: str
    message: str
    severity: str          # "high" | "medium" | "low"
    auto_fixable: bool
    suggested_fix_note: str = ""   # human-readable explanation of the fix
    code_snippet: str = ""         # the offending line(s), for the report
    meta: dict = field(default_factory=dict)  # rule-specific data the fixer needs

    def location(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass
class FixResult:
    """The outcome of attempting to auto-fix a bug."""
    bug: Bug
    applied: bool
    reason: str = ""   # why it wasn't applied, if applied=False
