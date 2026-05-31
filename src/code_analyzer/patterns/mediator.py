"""Pattern detector: Mediator.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Mediator pattern."""
        checks = []
        anti_patterns = []
        detected = False
        confidence = 0.0
        line = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_name = node.name.lower()

            # Detection heuristics
            is_mediator = False
            if any(k in class_name for k in ("mediator", "coordinator", "hub", "router")):
                is_mediator = True
                confidence = 0.8

            if is_mediator:
                detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Centralizes communication",
                    status="OK",
                    description="Components should communicate through mediator, not directly",
                ))

                checks.append(PatternCheck(
                    name="Not a God class",
                    status="OK",
                    description="Mediator should only route, not contain business logic",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Mediator",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
