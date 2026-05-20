"""Public API for the code_analyzer.analyzer package."""
from __future__ import annotations

import importlib
import pkgutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.analyzer.context import AnalysisContext
from code_analyzer.analyzer.scoring import wrap_criterion
from code_analyzer.analyzer import detectors as _detectors_pkg


def _autoload_detectors() -> None:
    """Import every module under ``detectors/`` so their @register decorators run."""
    for module_info in pkgutil.iter_modules(_detectors_pkg.__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{_detectors_pkg.__name__}.{module_info.name}")


_autoload_detectors()

from code_analyzer.analyzer.detectors import REGISTRY  # noqa: E402


def detect_all(ctx: AnalysisContext) -> Dict[str, Any]:
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


def run_analysis(filepath: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a full architecture analysis on *filepath* and return the result dict."""
    from code_analyzer.analyzer.core import ArchitectureAnalyzer, run_ruff, run_pylint

    file_path = Path(filepath)
    if not file_path.exists():
        return {"success": False, "error": f"Arquivo nao encontrado: {filepath}"}
    try:
        code = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Erro ao ler arquivo: {exc}"}

    analyzer = ArchitectureAnalyzer(code, filepath, config=config)
    result = analyzer.analyze()

    if result.get("success"):
        result["config"] = config or {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            ruff_future = executor.submit(run_ruff, filepath)
            pylint_future = executor.submit(run_pylint, filepath)
            ruff_result = ruff_future.result(timeout=25)
            pylint_result = pylint_future.result(timeout=25)
        result["tool_findings"] = {
            "ruff": ruff_result["findings"],
            "pylint": pylint_result["findings"],
            "total": len(ruff_result["findings"]) + len(pylint_result["findings"]),
        }
        warnings: List[str] = []
        if not ruff_result["available"]:
            warnings.append("ruff nao instalado — analise parcial")
        if not pylint_result["available"]:
            warnings.append("pylint nao instalado — analise parcial")
        if warnings:
            result["tool_warnings"] = warnings

    return result


def prune_criteria(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Remove criteria with no findings to reduce payload size."""
    if not isinstance(analysis, dict) or "criteria" not in analysis:
        return analysis
    criteria = analysis["criteria"]
    if not isinstance(criteria, dict):
        return analysis
    result = dict(analysis)
    result["criteria"] = {k: v for k, v in criteria.items() if v.get("findings")}
    return result
