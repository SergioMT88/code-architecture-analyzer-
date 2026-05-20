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


def production_risk_score(
    metrics: Dict[str, Any],
    criteria: Dict[str, Any],
    test_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute a production risk score (0-100, higher = safer).

    Weighted from four factors:
    - test coverage (higher → safer)
    - cyclomatic complexity (higher → riskier)
    - unique imports / coupling (higher → riskier)
    - ALTA-severity criteria with findings (higher → riskier)
    """
    coverage = test_analysis.get("estimated_coverage", 0)
    avg_complexity = metrics.get("avg_cyclomatic_complexity", 0)
    unique_imports = metrics.get("num_imports", 0)
    alta_count = sum(1 for v in criteria.values()
                     if v.get("severity") == "ALTA" and v.get("findings"))

    s_coverage = min(coverage / 80, 1.0) * 25
    s_complexity = max(0, (20 - avg_complexity) / 20) * 25
    s_coupling = max(0, (15 - unique_imports) / 15) * 25
    s_alta = max(0, (3 - alta_count) / 3) * 25

    score = round(s_coverage + s_complexity + s_coupling + s_alta, 1)

    if score >= 85:
        label = "Seguro"
    elif score >= 65:
        label = "Moderado"
    elif score >= 40:
        label = "Risco"
    else:
        label = "Critico"

    return {
        "score": score,
        "label": label,
        "components": {
            "coverage": round(s_coverage, 1),
            "complexity": round(s_complexity, 1),
            "coupling": round(s_coupling, 1),
            "alta_criteria": round(s_alta, 1),
        },
    }
