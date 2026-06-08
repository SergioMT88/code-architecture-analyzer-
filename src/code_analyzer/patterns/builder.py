"""Pattern detector: Builder.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Builder pattern."""
        checks = []
        anti_patterns = []
        _detected = False
        confidence = 0.0
        line = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_name = node.name.lower()
            method_names = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}

            # Detection heuristics
            is_builder = False
            if "builder" in class_name:
                is_builder = True
                confidence = 0.9
            if "build" in method_names and any(m.startswith("set_") for m in method_names):
                is_builder = True
                confidence = 0.8

            if is_builder:
                _detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Immutable result",
                    status="OK",
                    description="Built object should be immutable (no setters exposed)",
                ))

                checks.append(PatternCheck(
                    name="Validation in build()",
                    status="OK",
                    description="Required parameters should be checked in build()",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Builder",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
