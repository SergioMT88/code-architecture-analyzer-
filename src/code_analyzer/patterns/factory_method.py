"""Pattern detector: Factory Method.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Factory Method pattern."""
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
            is_factory = False
            if any(k in class_name for k in ("factory", "builder")):
                is_factory = True
                confidence = 0.85
            if method_names.intersection({"create", "build", "make", "produce"}):
                is_factory = True
                confidence = 0.75

            if is_factory:
                detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Returns interface/abstraction
                returns_concrete = False
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name in {"create", "build", "make"}:
                        for child in ast.walk(method):
                            if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
                                if isinstance(child.value.func, ast.Name):
                                    # If returns a concrete class name, it's a flag
                                    returns_concrete = True
                checks.append(PatternCheck(
                    name="Returns interface",
                    status="FLAG" if returns_concrete else "OK",
                    description="Factory should return interface/abstraction, not concrete type",
                ))

                # Check 2: Extensible (no infinite if/else)
                has_long_if_chain = False
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        if_count = sum(1 for child in ast.walk(method) if isinstance(child, ast.If))
                        if if_count > 3:
                            has_long_if_chain = True
                checks.append(PatternCheck(
                    name="Extensible",
                    status="FLAG" if has_long_if_chain else "OK",
                    description="Factory should be extensible without modifying existing code (OCP)",
                ))

                # Anti-patterns
                if has_long_if_chain:
                    anti_patterns.append(AntiPattern(
                        pattern="Factory",
                        anti_pattern="Infinite if/else chain",
                        severity="ALTA",
                        line=node.lineno,
                        issue="Factory with growing if/else chain violates Open/Closed Principle",
                        fix="Use Registry pattern or polymorphic dispatch instead of if/else",
                    ))

                if returns_concrete:
                    anti_patterns.append(AntiPattern(
                        pattern="Factory",
                        anti_pattern="Returns concrete type",
                        severity="MEDIA",
                        line=node.lineno,
                        issue="Factory returns concrete class instead of interface/abstraction",
                        fix="Define an interface/ABC and return that instead",
                    ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Factory",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
