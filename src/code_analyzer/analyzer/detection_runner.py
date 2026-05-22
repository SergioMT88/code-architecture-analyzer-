"""Detection runner — autoloads detectors and runs detect_all, breaking the
circular import between analyzer/__init__ and analyzer/core.py."""
from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, Dict

_log = logging.getLogger(__name__)

from code_analyzer.analyzer import detectors as _detectors_pkg
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
    """Run every registered detector against *ctx* and return a criteria dict."""
    criteria: Dict[str, Any] = {}
    for detector_cls in REGISTRY:
        d = detector_cls()
        if ctx.is_ignored(d.name):
            continue
        findings = d.detect(ctx)
        criteria[d.name] = wrap_criterion(
            name=d.name,
            severity=d.severity,
            description=d.description,
            findings=[f.to_dict() for f in findings],
            penalty_per_finding=d.penalty_per_finding,
        )
    return criteria
