"""Scoring utilities shared across detectors and the analysis pipeline."""
from __future__ import annotations

import math
from typing import Any, Dict, List


def score_to_status(score: int) -> str:
    if score >= 9:
        return "OK"
    if score >= 7:
        return "PARCIAL"
    if score >= 5:
        return "VIOLACAO"
    return "CRITICO"


def maintainability_index(lines: List[str], cyclomatic_complexity: float, functions_count: int) -> float:
    loc = max(1, len([ln for ln in lines if ln.strip()]))
    comments = len([ln for ln in lines if ln.strip().startswith("#")])
    cm = comments / max(1, loc) * 100
    mi = (
        171
        - 5.2 * math.log(max(1, loc))
        - 0.23 * cyclomatic_complexity
        - 16.2 * math.log(max(1, loc))
        + 50 * math.sin(math.sqrt(2.4 * cm))
    )
    return round(max(0, min(100, mi)), 1)


def mi_grade(mi: float) -> str:
    if mi >= 85:
        return "A (Excellent)"
    if mi >= 65:
        return "B (Good)"
    if mi >= 40:
        return "C (Moderate)"
    return "D (Poor - needs refactoring)"


def wrap_criterion(
    name: str,
    severity: str,
    description: str,
    findings: List[Dict[str, Any]],
    penalty_per_finding: int = 2,
) -> Dict[str, Any]:
    score = max(0, 10 - len(findings) * penalty_per_finding)
    return {
        "score": score,
        "status": score_to_status(score),
        "findings": findings,
        "severity": severity,
        "description": description,
    }
