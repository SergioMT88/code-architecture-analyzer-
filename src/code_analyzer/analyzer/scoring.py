"""Scoring utilities shared across detectors and the analysis pipeline."""
from __future__ import annotations

import ast
import math
from typing import Any, Dict, List, Optional


def score_to_status(score: int) -> str:
    if score >= 9:
        return "OK"
    if score >= 7:
        return "PARCIAL"
    if score >= 5:
        return "VIOLACAO"
    return "CRITICO"


def halstead_volume(tree: Optional[ast.AST]) -> float:
    if tree is None:
        return 1.0
    operators: List[str] = []
    operands: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            operators.append(type(node.op).__name__)
        elif isinstance(node, ast.UnaryOp):
            operators.append(type(node.op).__name__)
        elif isinstance(node, ast.BoolOp):
            operators.append(type(node.op).__name__)
        elif isinstance(node, ast.Compare):
            operators.extend(type(op).__name__ for op in node.ops)
        elif isinstance(node, ast.Assign):
            operators.append("Assign")
        elif isinstance(node, ast.AugAssign):
            operators.append(type(node.op).__name__ + "=")
        elif isinstance(node, ast.Call):
            operators.append("Call")
        elif isinstance(node, ast.Name):
            operands.append(node.id)
        elif isinstance(node, ast.Constant):
            operands.append(repr(node.value))
        elif isinstance(node, ast.Attribute):
            operands.append(node.attr)
    n1 = max(1, len(set(operators)))
    n2 = max(1, len(set(operands)))
    big_n = max(1, len(operators) + len(operands))
    return big_n * math.log2(n1 + n2)


def maintainability_index(
    lines: List[str],
    cyclomatic_complexity: float,
    functions_count: int,
    tree: Optional[ast.AST] = None,
) -> float:
    loc = max(1, len([ln for ln in lines if ln.strip()]))
    comments = len([ln for ln in lines if ln.strip().startswith("#")])
    cm = comments / max(1, loc)  # ratio 0-1 (formula expects ratio, not percentage)
    hv = max(1.0, halstead_volume(tree))
    avg_cc = cyclomatic_complexity / max(1, functions_count)
    mi = (
        171
        - 5.2 * math.log(hv)
        - 0.23 * avg_cc
        - 16.2 * math.log(loc)
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
    test_pain: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute a production risk score (0-100, higher = safer).

    Weighted from five factors (20 pts each):
    - test coverage (higher → safer)
    - cyclomatic complexity (higher → riskier)
    - unique imports / coupling (higher → riskier)
    - ALTA-severity criteria with findings (higher → riskier)
    - test pain (higher → safer) — v5.0.0
    """
    coverage = test_analysis.get("estimated_coverage", 0)
    avg_complexity = metrics.get("avg_cyclomatic_complexity", 0)
    unique_imports = metrics.get("num_imports", 0)
    alta_count = sum(1 for v in criteria.values()
                     if v.get("severity") == "ALTA" and v.get("findings"))

    s_coverage = min(coverage / 80, 1.0) * 20
    s_complexity = max(0, (20 - avg_complexity) / 20) * 20
    s_coupling = max(0, (15 - unique_imports) / 15) * 20
    s_alta = max(0, (3 - alta_count) / 3) * 20
    s_test_pain = (test_pain.get("aggregate", 50) / 100) * 20 if test_pain else 20

    score = round(s_coverage + s_complexity + s_coupling + s_alta + s_test_pain, 1)

    if score >= 85:
        label = "Seguro"
    elif score >= 65:
        label = "Bom"
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
            "test_pain": round(s_test_pain, 1),
        },
    }
