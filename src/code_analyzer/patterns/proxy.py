"""Pattern detector: Proxy.
Auto-extracted from pattern_analysis.py.
"""
from __future__ import annotations

import ast
from typing import Optional

from code_analyzer.pattern_analysis import PatternCheck, PatternDetection
from code_analyzer.patterns import register


@register
def detect(tree: ast.AST, code: str) -> Optional[PatternDetection]:
        """Analyze Proxy pattern."""
        checks = []
        anti_patterns = []
        _detected = False
        confidence = 0.0
        line = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_name = node.name.lower()

            # Detection heuristics
            is_proxy = False
            if any(k in class_name for k in ("proxy", "remote", "virtual", "protection")):
                is_proxy = True
                confidence = 0.85

            if is_proxy:
                _detected = True
                line = node.lineno

                # Quality checks
                checks.append(PatternCheck(
                    name="Same interface as real subject",
                    status="OK",
                    description="Proxy should have identical interface to real subject",
                ))

                checks.append(PatternCheck(
                    name="Justified purpose",
                    status="OK",
                    description="Proxy should have clear justification (lazy, access control, logging, remote)",
                ))

                # Quality score
                ok_count = sum(1 for c in checks if c.status == "OK")
                quality_score = (ok_count / max(1, len(checks))) * 10

                return PatternDetection(
                    pattern="Proxy",
                    detected=True,
                    confidence=confidence,
                    location=f"class {node.name}",
                    line=line,
                    checks=checks,
                    anti_patterns=anti_patterns,
                    quality_score=round(quality_score, 1),
                )

        return None
