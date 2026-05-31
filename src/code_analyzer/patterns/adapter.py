"""Pattern detector: Adapter.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Adapter pattern."""
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
            attr_names = {a.targets[0].id for a in node.body if isinstance(a, ast.Assign) and isinstance(a.targets[0], ast.Name)}

            # Detection heuristics
            is_adapter = False
            if any(k in class_name for k in ("adapter", "wrapper")):
                is_adapter = True
                confidence = 0.85
            if {"adaptee", "wrapped", "delegate", "target"}.intersection(attr_names):
                is_adapter = True
                confidence = 0.8

            if is_adapter:
                detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Conversion is unidirectional
                # Check for too many methods (might be doing too much)
                method_count = len(method_names)
                checks.append(PatternCheck(
                    name="Unidirectional conversion",
                    status="OK" if method_count < 10 else "FLAG",
                    description="Adapter should only convert, not add business logic",
                ))

                # Anti-patterns
                if method_count > 10:
                    anti_patterns.append(AntiPattern(
                        pattern="Adapter",
                        anti_pattern="Business logic mixed",
                        severity="MEDIA",
                        line=node.lineno,
                        issue="Adapter with too many methods may contain business logic",
                        fix="Keep adapter focused on conversion only",
                    ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Adapter",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
