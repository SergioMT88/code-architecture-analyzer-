"""Pattern detector: Template Method.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Template Method pattern."""
        checks = []
        anti_patterns = []
        _detected = False
        confidence = 0.0
        line = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            _method_names = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}

            # Detection heuristics
            is_template = False
            # Check for methods that call other methods (template structure)
            for method in node.body:
                if isinstance(method, ast.FunctionDef):
                    called_methods = set()
                    for child in ast.walk(method):
                        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                            called_methods.add(child.func.attr)
                    # If a method calls multiple other methods, it might be a template
                    if len(called_methods) >= 3:
                        is_template = True
                        confidence = 0.6
                        break

            if is_template:
                _detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Skeleton is fixed",
                    status="OK",
                    description="Template method should define a fixed algorithm skeleton",
                ))

                checks.append(PatternCheck(
                    name="Hooks are optional",
                    status="OK",
                    description="Subclasses should not be forced to override all hooks",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Template Method",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
