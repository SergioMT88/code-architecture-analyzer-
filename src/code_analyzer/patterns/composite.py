"""Pattern detector: Composite.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Composite pattern."""
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
            is_composite = False
            if any(k in class_name for k in ("composite", "tree", "node", "group")):
                is_composite = True
                confidence = 0.75
            # Check for methods that work with children
            if method_names.intersection({"add", "remove", "get_children", "children"}):
                is_composite = True
                confidence = 0.7

            if is_composite:
                detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Uniform interface",
                    status="OK",
                    description="Leaf and Composite should have same interface",
                ))

                checks.append(PatternCheck(
                    name="Operations work on tree",
                    status="OK",
                    description="Operations should work for 1 item or 1000 items",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Composite",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
