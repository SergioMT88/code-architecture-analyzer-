"""Analysis context passed to every detector."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AnalysisContext:
    """Immutable snapshot of a parsed file passed to all detectors."""

    code: str
    lines: List[str]
    filepath: str
    classes: Dict[str, Any]
    functions: List[Dict[str, Any]]
    imports: List[str]
    import_nodes: List[Dict[str, Any]]
    config: Dict[str, Any] = field(default_factory=dict)
    tree: Any = field(default=None)  # ast.Module, populated by core.py

    def get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def threshold(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    def is_ignored(self, criterion: str) -> bool:
        ignored = {str(item).strip().lower() for item in self.config.get("ignore_criteria", [])}
        return criterion.lower() in ignored
