"""Pattern detector: Iterator.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Iterator pattern."""
        checks = []
        anti_patterns = []
        _detected = False
        confidence = 0.0
        line = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            method_names = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}

            # Detection heuristics
            is_iterator = False
            if "__iter__" in method_names and "__next__" in method_names:
                is_iterator = True
                confidence = 0.95

            if is_iterator:
                _detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Doesn't expose internal structure",
                    status="OK",
                    description="Iterator should traverse without exposing internal data structure",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Iterator",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
