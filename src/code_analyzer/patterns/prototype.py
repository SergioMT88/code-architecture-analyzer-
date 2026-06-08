"""Pattern detector: Prototype.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Prototype pattern."""
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
            is_prototype = False
            if "clone" in method_names or "copy" in method_names:
                is_prototype = True
                confidence = 0.85

            if is_prototype:
                _detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Deep copy when needed",
                    status="OK",
                    description="Prototype should deep copy nested objects",
                ))

                # Anti-pattern: shallow copy
                has_shallow_copy = "copy" in code and "deep" not in code.lower()
                if has_shallow_copy:
                    anti_patterns.append(AntiPattern(
                        pattern="Prototype",
                        anti_pattern="Shallow copy",
                        severity="MEDIA",
                        line=node.lineno,
                        issue="Prototype using shallow copy may cause shared state issues",
                        fix="Use copy.deepcopy() for nested objects",
                    ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Prototype",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
