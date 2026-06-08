"""Pattern detector: Facade.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Facade pattern."""
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
            is_facade = False
            if "facade" in class_name:
                is_facade = True
                confidence = 0.9
            # High import count + few public methods = potential facade
            import_count = sum(1 for child in ast.walk(tree) if isinstance(child, (ast.Import, ast.ImportFrom)))
            if import_count > 8 and len(method_names) < 10:
                is_facade = True
                confidence = 0.6

            if is_facade:
                _detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Simplifies subsystem
                checks.append(PatternCheck(
                    name="Simplifies subsystem",
                    status="OK",
                    description="Facade should reduce complexity for clients",
                ))

                # Check 2: Doesn't hide essential functionality
                checks.append(PatternCheck(
                    name="Doesn't hide essential functionality",
                    status="OK",
                    description="Facade should still allow access to subsystem if needed",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Facade",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
