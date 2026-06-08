"""Pattern detector: Singleton.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Singleton pattern."""
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
            is_singleton = False
            if "__new__" in method_names:
                is_singleton = True
                confidence = 0.8
            if "singleton" in class_name or "_instance" in method_names:
                is_singleton = True
                confidence = 0.9
            if "instance" in method_names and ("get_instance" in method_names or "getInstance" in method_names):
                is_singleton = True
                confidence = 0.85

            if is_singleton:
                _detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Thread safety
                has_lock = "lock" in code.lower() or "_lock" in method_names or "synchronized" in code
                checks.append(PatternCheck(
                    name="Thread-safe",
                    status="OK" if has_lock else "FLAG",
                    description="Singleton should be thread-safe in multi-threaded environments",
                    line=node.lineno,
                ))

                # Check 2: Private constructor
                has_private_init = "_init" in method_names or "__init__" in method_names
                checks.append(PatternCheck(
                    name="Private constructor",
                    status="OK" if has_private_init else "FLAG",
                    description="Constructor should be private to prevent direct instantiation",
                    line=node.lineno,
                ))

                # Check 3: No exposed new
                has_exposed_new = any(
                    isinstance(child, ast.Assign)
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == node.name
                )
                checks.append(PatternCheck(
                    name="No exposed new",
                    status="OK" if not has_exposed_new else "FLAG",
                    description="Should not expose direct instantiation elsewhere",
                ))

                # Anti-patterns
                if not has_lock:
                    anti_patterns.append(AntiPattern(
                        pattern="Singleton",
                        anti_pattern="Not thread-safe",
                        severity="MEDIA",
                        line=node.lineno,
                        issue="Singleton without thread safety can cause issues in multi-threaded environments",
                        fix="Add threading.Lock or use metaclass with synchronization",
                    ))

                # Calculate quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Singleton",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
