"""Detector base class, Finding dataclass, and auto-discovery registry."""
from __future__ import annotations

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

    def to_dict(self) -> dict:
        return {
            "location": self.location,
            "issue": self.issue,
            "severity": self.severity,
            "line_content": self.line_content,
            "suggestion": self.suggestion,
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
