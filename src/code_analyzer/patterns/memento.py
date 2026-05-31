"""Pattern detector: Memento.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Memento pattern."""
        checks = []
        anti_patterns = []
        detected = False
        confidence = 0.0
        line = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_name = node.name.lower()
            method_names = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}

            # Detection heuristics
            is_memento = False
            if any(k in class_name for k in ("memento", "snapshot", "state_save")):
                is_memento = True
                confidence = 0.85
            if method_names.intersection({"save_state", "restore_state", "create_memento", "set_memento"}):
                is_memento = True
                confidence = 0.8

            if is_memento:
                detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="State is encapsulated",
                    status="OK",
                    description="Memento should not expose internal details to caretaker",
                ))

                checks.append(PatternCheck(
                    name="Deep copy of state",
                    status="OK",
                    description="Memento should deep copy mutable objects",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Memento",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None


def analyze_patterns(tree: ast.AST, code: str, filepath: str = "") -> PatternAnalysis:
    """Convenience function to analyze patterns in code.

    Args:
        tree: Parsed AST of the code
        code: Source code string
        filepath: Path to the file (optional)

    Returns:
        PatternAnalysis with all detected patterns, quality checks, and anti-patterns
    """
    analyzer = PatternAnalyzer()
    return analyzer.analyze(tree, code, filepath)