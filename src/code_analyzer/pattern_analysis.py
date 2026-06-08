"""Pattern Analysis — comprehensive design pattern detection and quality checks.

This module provides the "second layer" of analysis:
1. Detects all 20 classic design patterns
2. Checks quality of implementation
3. Identifies anti-patterns
4. Suggests improvements

Integrates with agent_review.py for the metacognitive prompt.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass
class PatternCheck:
    """Single quality check for a design pattern."""
    name: str
    status: str  # OK, FLAG, N/A
    description: str
    line: Optional[int] = None


@dataclass
class AntiPattern:
    """Detected anti-pattern in design pattern implementation."""
    pattern: str
    anti_pattern: str
    severity: str  # ALTA, MEDIA, BAIXA
    line: int
    issue: str
    fix: str


@dataclass
class PatternDetection:
    """Complete analysis result for a single pattern."""
    pattern: str
    detected: bool
    confidence: float  # 0.0 - 1.0
    location: Optional[str] = None
    line: Optional[int] = None
    checks: List[PatternCheck] = field(default_factory=list)
    anti_patterns: List[AntiPattern] = field(default_factory=list)
    quality_score: float = 0.0  # 0-10
    suggestion: Optional[str] = None


@dataclass
class PatternAnalysis:
    """Complete pattern analysis for a file."""
    file_path: str
    patterns: List[PatternDetection]
    total_detected: int = 0
    total_anti_patterns: int = 0
    overall_quality: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_detected": self.total_detected,
            "total_anti_patterns": self.total_anti_patterns,
            "overall_quality": self.overall_quality,
            "patterns": [
                {
                    "pattern": p.pattern,
                    "detected": p.detected,
                    "confidence": p.confidence,
                    "location": p.location,
                    "line": p.line,
                    "quality_score": p.quality_score,
                    "checks": [
                        {"name": c.name, "status": c.status, "description": c.description}
                        for c in p.checks
                    ],
                    "anti_patterns": [
                        {"pattern": a.pattern, "anti_pattern": a.anti_pattern, "severity": a.severity, "issue": a.issue}
                        for a in p.anti_patterns
                    ],
                    "suggestion": p.suggestion,
                }
                for p in self.patterns if p.detected
            ],
        }


class PatternAnalyzer:
    """Analyzes code for design pattern usage, quality, and anti-patterns.

    This is the "second layer" of analysis that complements the code quality
    checks (coupling, SRP, etc.) with design pattern analysis.
    """

    def analyze(self, tree: ast.AST, code: str, filepath: str = "") -> PatternAnalysis:
        """Run complete pattern analysis on the given code."""
        from code_analyzer.patterns import get_detectors

        patterns = []

        for detector in get_detectors():
            try:
                result = detector(tree, code)
                if result:
                    patterns.append(result)
            except Exception as e:  # pluggable detectors may raise anything
                _log.debug("Pattern detector failed: %s", e, exc_info=True)

        # Calculate summary
        detected = [p for p in patterns if p.detected]
        anti_patterns = []
        for p in patterns:
            anti_patterns.extend(p.anti_patterns)

        overall_quality = 0.0
        if detected:
            overall_quality = sum(p.quality_score for p in detected) / len(detected)

        return PatternAnalysis(
            file_path=filepath,
            patterns=patterns,
            total_detected=len(detected),
            total_anti_patterns=len(anti_patterns),
            overall_quality=round(overall_quality, 1),
        )


def analyze_patterns(tree: ast.AST, code: str, filepath: str = "") -> PatternAnalysis:
    """Convenience function for pattern analysis.

    Args:
        tree: Parsed AST of the code
        code: Source code string
        filepath: Path to the file being analyzed

    Returns:
        PatternAnalysis with all detected patterns, quality checks, and anti-patterns
    """
    analyzer = PatternAnalyzer()
    return analyzer.analyze(tree, code, filepath)
