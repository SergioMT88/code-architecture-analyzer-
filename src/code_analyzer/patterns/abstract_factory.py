"""Pattern detector: Abstract Factory.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Abstract Factory pattern."""
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
            is_abstract_factory = False
            if "abstract_factory" in class_name or "abstractfactory" in class_name:
                is_abstract_factory = True
                confidence = 0.9
            # Multiple create methods suggest family of products
            create_methods = [m for m in method_names if m.startswith("create")]
            if len(create_methods) >= 2:
                is_abstract_factory = True
                confidence = 0.7

            if is_abstract_factory:
                detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Creates coherent family",
                    status="OK",
                    description="Abstract Factory should create products that work together",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Abstract Factory",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
