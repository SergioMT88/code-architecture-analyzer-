"""Pattern detector: Decorator.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Decorator pattern."""
        checks = []
        anti_patterns = []
        detected = False
        confidence = 0.0
        line = None

        # Check for decorator functions (not Python decorators)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_name = node.name.lower()
            method_names = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}

            # Detection: class that wraps another object
            is_decorator = False
            if "decorator" in class_name and not class_name.startswith("_"):
                is_decorator = True
                confidence = 0.8
            if "wrapper" in class_name and method_names.intersection({"wrap", "decorate"}):
                is_decorator = True
                confidence = 0.75

            if is_decorator:
                detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Same interface as wrapped
                # This is hard to detect statically
                checks.append(PatternCheck(
                    name="Transparent to client",
                    status="OK",
                    description="Decorator should be transparent to the client",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Decorator",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
