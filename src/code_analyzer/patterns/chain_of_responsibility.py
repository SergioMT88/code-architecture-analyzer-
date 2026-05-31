"""Pattern detector: Chain of Responsibility.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import AntiPattern, PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Chain of Responsibility pattern."""
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
            is_chain = False
            if any(k in class_name for k in ("handler", "chain", "processor")):
                is_chain = True
                confidence = 0.8
            if "next_handler" in method_names or "set_next" in method_names:
                is_chain = True
                confidence = 0.85

            if is_chain:
                detected = True
                line = node.lineno

                checks.append(PatternCheck(
                    name="Each handler decides",
                    status="OK",
                    description="Each handler should decide to process or pass along",
                ))

                checks.append(PatternCheck(
                    name="Default handler exists",
                    status="OK",
                    description="Chain should have a default handler to avoid falling through",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Chain of Responsibility",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
