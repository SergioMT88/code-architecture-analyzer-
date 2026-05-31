"""Detection runner — autoloads detectors and runs detect_all, breaking the
circular import between analyzer/__init__ and analyzer/core.py."""
from __future__ import annotations

import importlib
import logging
import pkgutil
import time
from typing import Any, Dict, List, Tuple

from code_analyzer.constants import ASK_THRESHOLD

_SEVERITY_WEIGHT: Dict[str, int] = {"ALTA": 3, "MEDIA": 2, "BAIXA": 1}

_log = logging.getLogger(__name__)

from code_analyzer.analyzer import detectors as _detectors_pkg
from code_analyzer.analyzer.detectors import Finding
from code_analyzer.analyzer.scoring import wrap_criterion


def _autoload_detectors() -> None:
    """Import every module under ``detectors/`` so their @register decorators run."""
    for module_info in pkgutil.iter_modules(_detectors_pkg.__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{_detectors_pkg.__name__}.{module_info.name}")


_autoload_detectors()

from code_analyzer.analyzer.detectors import REGISTRY


def detect_all(ctx: "AnalysisContext") -> Dict[str, Any]:
    """Run every registered detector against *ctx* and return a criteria dict.

    Records per-detector wall time in ctx._detector_timings (list of (name, seconds)).
    Used by the report generator to surface slow detectors.
    """
    criteria: Dict[str, Any] = {}
    timings: List[Tuple[str, float]] = []
    for detector_cls in REGISTRY:
        d = detector_cls()
        if ctx.is_ignored(d.name):
            continue
        t0 = time.perf_counter()
        findings = d.detect(ctx)
        # Apply default_confidence to findings that haven't set it explicitly
        if d.default_confidence != 1.0:
            findings = [
                Finding(
                    criterion=f.criterion, location=f.location, line=f.line,
                    severity=f.severity, issue=f.issue, suggestion=f.suggestion,
                    line_content=f.line_content,
                    confidence=f.confidence if f.confidence != 1.0 else d.default_confidence,
                )
                if f.confidence == 1.0 else f
                for f in findings
            ]
        timings.append((d.name, time.perf_counter() - t0))
        criteria[d.name] = wrap_criterion(
            name=d.name,
            severity=d.severity,
            description=d.description,
            findings=[f.to_dict(ctx.filepath) for f in findings],
            penalty_per_finding=d.penalty_per_finding,
        )
    setattr(ctx, "_detector_timings", timings)
    return criteria


def build_question_queue(
    criteria: Dict[str, Any],
    limit: int = 3,
    intent_store: "Any | None" = None,
) -> List[Dict[str, Any]]:
    """Return up to *limit* findings with confidence < ASK_THRESHOLD, ranked by impact.

    Impact = penalty_per_finding * severity_weight.  Findings already answered
    in *intent_store* (IL4) are skipped — they don't need to be asked again.
    """
    candidates: List[Dict[str, Any]] = []

    for criterion_name, criterion in criteria.items():
        penalty = criterion.get("penalty_per_finding", 2)
        severity = criterion.get("severity", "MEDIA")
        weight = _SEVERITY_WEIGHT.get(severity, 2)
        impact = penalty * weight

        for finding in criterion.get("findings", []):
            fid = finding.get("finding_id", "")
            if intent_store is not None and intent_store.get(fid) is not None:
                continue
            conf = finding.get("confidence", 1.0)
            if conf >= ASK_THRESHOLD:
                continue
            candidates.append({
                "finding_id": fid,
                "criterion": criterion_name,
                "location": finding.get("location", ""),
                "line": finding.get("line", 0),
                "line_content": finding.get("line_content", ""),
                "issue": finding.get("issue", ""),
                "suggestion": finding.get("suggestion", ""),
                "confidence": conf,
                "impact": impact,
                "severity": severity,
            })

    candidates.sort(key=lambda q: q["impact"], reverse=True)
    return candidates[:limit]
