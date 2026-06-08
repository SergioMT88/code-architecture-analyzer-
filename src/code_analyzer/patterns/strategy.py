"""Pattern detector: Strategy.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Strategy pattern."""
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
            base_names = {base.split(".")[-1] for base in (
                base.id if isinstance(base, ast.Name) else
                base.attr if isinstance(base, ast.Attribute) else ""
                for base in (node.bases or [])
            )}

            # Detection heuristics
            is_strategy = False
            if "strategy" in class_name:
                is_strategy = True
                confidence = 0.9
            if base_names.intersection({"ABC", "Protocol", "Strategy"}) and method_names.intersection({"execute", "run", "apply", "process"}):
                is_strategy = True
                confidence = 0.8

            if is_strategy:
                _detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Family is interchangeable
                has_same_interface = base_names.intersection({"ABC", "Protocol"})
                checks.append(PatternCheck(
                    name="Interchangeable family",
                    status="OK" if has_same_interface else "FLAG",
                    description="Strategy implementations should have same interface",
                ))

                # Check 2: Context delegates behavior
                # This is harder to detect statically, check for if/else dispatch
                has_if_dispatch = False
                for child in ast.walk(tree):
                    if isinstance(child, ast.If):
                        for comparison in ast.walk(child.test):
                            if isinstance(comparison, ast.Compare):
                                has_if_dispatch = True
                checks.append(PatternCheck(
                    name="No if/else dispatch",
                    status="FLAG" if has_if_dispatch else "OK",
                    description="Context should delegate to strategy, not use if/else",
                ))

                # Anti-patterns
                if has_if_dispatch:
                    anti_patterns.append(AntiPattern(
                        pattern="Strategy",
                        anti_pattern="if/else dispatch",
                        severity="MEDIA",
                        line=node.lineno,
                        issue="Using if/else to select strategy defeats the purpose",
                        fix="Use dictionary mapping or dependency injection",
                    ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Strategy",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
