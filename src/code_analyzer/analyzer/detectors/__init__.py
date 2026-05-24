"""Detector base class, Finding dataclass, and auto-discovery registry."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Type

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

REGISTRY: List[Type["Detector"]] = []


def register(cls: Type["Detector"]) -> Type["Detector"]:
    """Class decorator that adds a detector to the global registry."""
    REGISTRY.append(cls)
    return cls


def _finding_hash(filepath: str, criterion: str, line_content: str) -> str:
    """Stable 8-char hex ID for a finding — used for suppression tracking.

    Stable across runs as long as the source line and criterion don't change.
    Changing line numbers (e.g. inserting lines above) does NOT change the hash.
    """
    raw = f"{filepath}|{criterion}|{line_content.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


@dataclass(frozen=True)
class Finding:
    """A single actionable problem found in the analyzed code."""

    criterion: str
    location: str
    line: int
    severity: str  # "ALTA" | "MEDIA" | "BAIXA"
    issue: str
    suggestion: str
    line_content: str = ""
    # 0.0–1.0: how certain this finding is. < 0.7 triggers a clarifying question in
    # Intent Learning sessions; >= 0.85 is emitted directly without asking the user.
    confidence: float = 1.0

    def to_dict(self, filepath: str = "") -> dict:
        return {
            "finding_id": _finding_hash(filepath, self.criterion, self.line_content),
            "location": self.location,
            "issue": self.issue,
            "severity": self.severity,
            "line_content": self.line_content,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }


class Detector(ABC):
    """Abstract base for all architecture detectors."""

    name: str = ""
    severity: str = "MEDIA"
    description: str = ""
    penalty_per_finding: int = 2

    @abstractmethod
    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        ...
