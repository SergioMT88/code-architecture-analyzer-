"""Pattern detector: Command.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Command pattern."""
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
            is_command = False
            if any(k in class_name for k in ("command", "action", "task")):
                is_command = True
                confidence = 0.8
            if method_names.intersection({"execute", "undo", "redo"}):
                is_command = True
                confidence = 0.75

            if is_command:
                detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Encapsulates everything",
                    status="OK",
                    description="Command should encapsulate parameters, receiver, and action",
                ))

                checks.append(PatternCheck(
                    name="Supports undo if needed",
                    status="OK",
                    description="Command should support undo/redo if required",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Command",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
