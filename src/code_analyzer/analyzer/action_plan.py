"""Action plan — enriches findings into agent-ready ActionRecords.

Transforms raw detector findings into structured, executable action records
that an AI coding agent can consume directly — with provenance, blast radius,
test coverage, confidence, suggested diffs, and verification steps.

v7.0.0 — Caminho das Pedras (Agent-Ready Output).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.constants import HIGH_CONFIDENCE, MEDIUM_CONFIDENCE


@dataclass
class VerifyStep:
    """A verification step to run after applying a fix."""
    kind: str  # "test" | "lint" | "missing_test" | "manual"
    cmd: Optional[str] = None   # e.g. "pytest tests/test_x.py::test_y"
    spec: Optional[str] = None  # e.g. "should raise ValueError on empty input"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"kind": self.kind}
        if self.cmd:
            d["cmd"] = self.cmd
        if self.spec:
            d["spec"] = self.spec
        return d


@dataclass
class ActionRecord:
    """A single actionable finding enriched with execution context for agents.

    Six dimensions (v7.0 spec):
    - provenance: where the value comes from
    - blast_radius: other files that call or are called by this code
    - tests_covering: existing tests that exercise this code path
    - confidence: 0.0-1.0 how certain the tool is
    - diff: suggested code change as unified diff
    - verification: steps to run after applying the fix
    """
    id: str
    criterion: str
    summary: str
    location: str
    line: int
    severity: str  # ALTA | MEDIA | BAIXA
    issue: str
    suggestion: str
    line_content: str = ""

    # ── enriched dimensions ──────────────────────────────────────────────
    confidence: float = 1.0
    provenance: Optional[str] = None
    blast_radius: List[str] = field(default_factory=list)
    callers: List[str] = field(default_factory=list)
    tests_covering: List[str] = field(default_factory=list)
    diff: Optional[str] = None
    risk_level: str = "safe"  # "safe" | "caution" | "dangerous"
    verify: List[VerifyStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "criterion": self.criterion,
            "summary": self.summary,
            "location": self.location,
            "line": self.line,
            "severity": self.severity,
            "issue": self.issue,
            "suggestion": self.suggestion,
            "line_content": self.line_content,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
        }
        if self.provenance:
            d["provenance"] = self.provenance
        if self.blast_radius:
            d["blast_radius"] = self.blast_radius
        if self.callers:
            d["callers"] = self.callers
        if self.tests_covering:
            d["tests_covering"] = self.tests_covering
        if self.diff:
            d["diff"] = self.diff
        if self.verify:
            d["verify"] = [v.to_dict() for v in self.verify]
        return d


# ── severity → risk_level mapping ──────────────────────────────────────────
_SEVERITY_RISK: Dict[str, str] = {
    "ALTA": "dangerous",
    "MEDIA": "caution",
    "BAIXA": "safe",
}


def _compute_risk_level(severity: str, confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE and severity == "BAIXA":
        return "safe"
    if severity == "ALTA":
        return "dangerous"
    if severity == "MEDIA" or confidence < MEDIUM_CONFIDENCE:
        return "caution"
    return "safe"


def _build_summary(finding: Dict[str, Any]) -> str:
    suggestion = finding.get("suggestion", "")
    issue = finding.get("issue", "")
    if suggestion:
        return suggestion[:200]
    return issue[:200]


def _build_provenance(finding: Dict, purity_map: Dict, dataflow_results: List) -> Optional[str]:
    """Try to extract provenance from dataflow analysis."""
    location = finding.get("location", "")
    line = finding.get("line", 0)
    criterion = finding.get("criterion", "")

    if criterion == "DictGet":
        return _provenance_dict_get(finding, purity_map, dataflow_results)
    if criterion == "InjectionRisk":
        return _provenance_injection_risk(finding, dataflow_results)

    # Generic: check if this line appears in any dataflow trace
    for df in dataflow_results:
        func_name = df.get("name", "")
        stmts = df.get("statements", [])
        for stmt in stmts:
            slo = stmt.get("lineno", 0)
            selo = stmt.get("end_lineno", slo)
            if slo <= line <= selo:
                defs = stmt.get("defs", [])
                uses = stmt.get("uses", [])
                if uses:
                    return f"variables used: {', '.join(sorted(uses))} in {func_name}()"
                if defs:
                    return f"variables defined: {', '.join(sorted(defs))} in {func_name}()"

    return None


def _provenance_dict_get(finding: Dict, purity_map: Dict, dataflow_results: List) -> Optional[str]:
    """Provenance for DictGet: identify whether dict comes from external source."""
    line_content = finding.get("line_content", "")
    if not line_content:
        return None
    # Check common patterns
    external_sources = [
        "json.loads", "json.load", ".json()", "request.data",
        "request.POST", "request.GET", "request.FILES",
        "os.environ", "environ.get", "payload",
    ]
    for src in external_sources:
        if src in line_content.lower():
            return f"data originates from {src}"
    return None


def _provenance_injection_risk(finding: Dict, dataflow_results: List) -> Optional[str]:
    """Provenance for InjectionRisk: trace f-string input."""
    line_content = finding.get("line_content", "")
    if not line_content:
        return None
    if "f\"" in line_content or "f'" in line_content:
        match = re.search(r'\{([^}]+)\}', line_content)
        if match:
            return f"user-controlled input via f-string interpolation: {{{match.group(1)}}}"
    return None


def _find_callers(filepath: str, deps: Dict, project_context: Dict) -> List[str]:
    """Find files that import this module."""
    callers = []
    fan_in_data = project_context.get("fan_in_modules", [])
    for mod in fan_in_data:
        if isinstance(mod, str):
            callers.append(mod)
    return callers[:5]


def _find_tests(filepath: str, test_pain: Dict, test_analysis: Dict, finding: Dict) -> List[str]:
    """Find test functions that cover this finding's location."""
    tests = []
    tp_details = test_pain.get("details", {})

    # Check if test pain found test coverage
    coverage_data = tp_details.get("coverage", {})
    covered_funcs = coverage_data.get("covered_functions", [])

    # Match finding location to covered functions
    line = finding.get("line", 0)
    for func_entry in covered_funcs:
        if isinstance(func_entry, dict):
            flo = func_entry.get("lineno", 0)
            felo = func_entry.get("end_lineno", flo)
            if flo <= line <= felo:
                test_funcs = func_entry.get("tested_by", [])
                tests.extend(test_funcs)

    # Fallback: use estimated coverage from test_analysis
    if not tests and test_analysis.get("estimated_coverage", 0) > 0:
        missing = test_analysis.get("missing_tests", [])
        if missing:
            pass  # No specific test found

    return tests[:3]


# Detector criteria that map to a REAL ruff rule code. Only these get a runnable
# `ruff check --select=<CODE>` step; the rest are architectural/semantic and ruff
# has no rule for them, so emitting `--select=<DetectorName>` would just error.
_RUFF_CODE_FOR: Dict[str, str] = {
    "BareExcept": "E722",
    "MutableDefault": "B006",
    "WildcardImport": "F403",
    "UnusedVariable": "F841",
    "NoneComparison": "E711",
    "TypeIsInstance": "E721",
    "PrintLeak": "T201",
    "ManyParameters": "PLR0913",
    "RangeLenLoop": "B007",
}


def _build_verify_steps(finding: Dict, criterion: str = "", filepath: str = "") -> List[VerifyStep]:
    """Generate runnable verification steps for a finding.

    A ruff step is emitted only when the criterion has a genuine ruff rule code;
    otherwise we fall back to a test or manual step rather than a malformed command.
    """
    steps: List[VerifyStep] = []
    criterion = criterion or finding.get("criterion", "")
    line_content = finding.get("line_content", "").strip()
    target = f" {filepath}" if filepath else ""

    ruff_code = _RUFF_CODE_FOR.get(criterion)
    if ruff_code:
        steps.append(VerifyStep(kind="lint", cmd=f"ruff check --select={ruff_code}{target}"))

    # Criterion-specific verification
    if criterion == "DictGet":
        key_match = re.search(r'\[[\'"]([^\]]+)[\'"]\]', line_content)
        key = key_match.group(1) if key_match else "key"
        steps.append(VerifyStep(
            kind="missing_test",
            spec=f"should handle missing key '{key}' gracefully",
        ))
    elif criterion == "HardcodedSecrets":
        steps.append(VerifyStep(kind="missing_test", spec="should load secret from environment"))
    elif criterion == "InjectionRisk":
        steps.append(VerifyStep(kind="missing_test", spec="should reject malicious input"))
    elif criterion == "ContextManagerLeak":
        steps.append(VerifyStep(kind="missing_test", spec="should close resource on exception"))
    elif criterion == "BareExcept":
        steps.append(VerifyStep(kind="missing_test", spec="should handle specific exception types"))
    elif criterion in ("Coupling", "SRP", "GodClass", "Cohesion", "InterfaceSegregation",
                        "DeepNesting", "FeatureEnvy", "LSP"):
        steps.append(VerifyStep(kind="test", cmd="pytest"))

    # Fallback: never return an empty / no-op verification.
    if not steps:
        steps.append(VerifyStep(kind="manual", spec="revisar a mudanca e rodar a suite de testes"))

    return steps


def _extract_line_content(lines: List[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


def build_action_records(
    filepath: str,
    analysis: Dict[str, Any],
    lines: Optional[List[str]] = None,
) -> List[ActionRecord]:
    """Build enriched ActionRecords from raw analysis criteria.

    Args:
        filepath: Path to the analyzed Python file.
        analysis: Full analysis dict from run_analysis().
        lines: Source lines (optional). If None, inferred from analysis payload.

    Returns:
        List of ActionRecords sorted by priority (ALTA first, then by impact).
    """
    records: List[ActionRecord] = []
    criteria = analysis.get("criteria", {})
    purity_map = analysis.get("purity_map", {})
    dataflow_results = analysis.get("dataflow_results", [])
    test_pain = analysis.get("test_pain", {})
    test_analysis = analysis.get("test_analysis", {})
    project_context = analysis.get("project_context", {})
    deps = analysis.get("dependencies", {})

    if lines is None:
        # Try to extract lines from analysis payload if available
        metrics = analysis.get("metrics", {})
        lines = []  # caller should provide lines

    for criterion_name, criterion_data in criteria.items():
        findings = criterion_data.get("findings", [])
        if not findings:
            continue

        for finding in findings:
            finding_id = finding.get("finding_id", "")
            line = finding.get("line", finding.get("lineno", 0))
            severity = finding.get("severity", criterion_data.get("severity", "MEDIA"))
            confidence = finding.get("confidence", 1.0)
            suggestion = finding.get("suggestion", "")
            issue = finding.get("issue", "")
            location = finding.get("location", "")
            line_content = finding.get("line_content", "")

            record = ActionRecord(
                id=finding_id,
                criterion=criterion_name,
                summary=_build_summary(finding),
                location=location,
                line=line,
                severity=severity,
                issue=issue,
                suggestion=suggestion,
                line_content=line_content,
                confidence=confidence,
                risk_level=_compute_risk_level(severity, confidence),
                provenance=_build_provenance(finding, purity_map, dataflow_results),
                callers=_find_callers(filepath, deps, project_context),
                blast_radius=[],
                tests_covering=_find_tests(filepath, test_pain, test_analysis, finding),
                verify=_build_verify_steps(finding, criterion_name, filepath),
            )
            records.append(record)

    # Sort: severity (ALTA first), then confidence (low first = most uncertain first)
    severity_order = {"ALTA": 0, "MEDIA": 1, "BAIXA": 2}
    records.sort(key=lambda r: (
        severity_order.get(r.severity, 9),
        r.confidence,  # low confidence first → needs human/agent decision
    ))

    return records


def generate_agent_json(
    filepath: str,
    analysis: Dict[str, Any],
    il_answer_count: int = 0,
) -> str:
    """Generate JSON output for AI coding agents with full ActionRecords.

    This is the primary output format for agent mode (--agent flag).
    """
    import json as _json

    criteria = analysis.get("criteria", {})
    scores = {k: v.get("score", 10) for k, v in criteria.items()}
    metrics = analysis.get("metrics", {})

    records = build_action_records(filepath, analysis)

    # ── Categorize ──────────────────────────────────────────────────────────
    criticals = [r for r in records if r.severity == "ALTA"]
    warnings_list = [r for r in records if r.severity == "MEDIA"]
    safe_list = [r for r in records if r.risk_level == "safe" and r.confidence >= HIGH_CONFIDENCE]

    # ── Build payload ───────────────────────────────────────────────────────
    payload: Dict[str, Any] = {
        "file": filepath,
        "score": {
            "overall": round(metrics.get("maintainability_index", 0), 1),
            "grade": metrics.get("maintainability_grade", ""),
            "production_risk": analysis.get("production_risk", {}),
            "per_criterion": scores,
        },
        "metrics": {
            "lines_of_code": metrics.get("lines_of_code", 0),
            "num_classes": metrics.get("num_classes", 0),
            "num_functions": metrics.get("num_functions", 0),
            "avg_complexity": metrics.get("avg_cyclomatic_complexity", 0),
            "comment_ratio": metrics.get("comment_ratio", 0),
        },
        "action_records": [r.to_dict() for r in records],
        "summary": {
            "total_findings": len(records),
            "critical": len(criticals),
            "warnings": len(warnings_list),
            "safe_auto_apply": len(safe_list),
        },
        "intent_learning": {
            "answers_recorded": il_answer_count,
            "noisy_detectors": [
                n for n, v in criteria.items() if v.get("noisy")
            ],
        },
    }

    return _json.dumps(payload, ensure_ascii=False, default=str, indent=2)
