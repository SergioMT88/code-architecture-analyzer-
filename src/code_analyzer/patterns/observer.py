"""Pattern detector: Observer.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Observer pattern."""
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
            is_observer = False
            if any(k in class_name for k in ("observer", "listener", "subscriber", "event")):
                is_observer = True
                confidence = 0.85
            if method_names.intersection({"subscribe", "unsubscribe", "notify", "on_event", "add_listener", "remove_listener"}):
                is_observer = True
                confidence = 0.8

            if is_observer:
                detected = True
                line = node.lineno

                # Quality checks
                # Check 1: Has unsubscribe mechanism
                has_unsubscribe = method_names.intersection({"unsubscribe", "remove_listener", "detach", "off"})
                checks.append(PatternCheck(
                    name="Unsubscribe mechanism",
                    status="OK" if has_unsubscribe else "FLAG",
                    description="Observer should have unsubscribe to prevent memory leaks",
                ))

                # Check 2: Notify in try/catch
                has_try_catch = False
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name == "notify":
                        for child in ast.walk(method):
                            if isinstance(child, ast.Try):
                                has_try_catch = True
                checks.append(PatternCheck(
                    name="Error handling in notify",
                    status="OK" if has_try_catch else "FLAG",
                    description="Notify should catch exceptions to prevent one observer from breaking others",
                ))

                # Anti-patterns
                if not has_unsubscribe:
                    anti_patterns.append(AntiPattern(
                        pattern="Observer",
                        anti_pattern="Memory leak",
                        severity="ALTA",
                        line=node.lineno,
                        issue="Observer without unsubscribe can cause memory leaks",
                        fix="Add unsubscribe/remove method and document lifecycle",
                    ))

                if not has_try_catch:
                    anti_patterns.append(AntiPattern(
                        pattern="Observer",
                        anti_pattern="Synchronous blocking",
                        severity="MEDIA",
                        line=node.lineno,
                        issue="Notify without error handling can block all observers on failure",
                        fix="Wrap observer notification in try/except",
                    ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Observer",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
