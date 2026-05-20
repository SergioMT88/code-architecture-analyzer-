"""Public API for the code_analyzer.analyzer package."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.analyzer.context import AnalysisContext
from code_analyzer.analyzer.scoring import wrap_criterion

# Import all detector modules so their @register decorators fire and populate REGISTRY.
import code_analyzer.analyzer.detectors.srp  # noqa: F401
import code_analyzer.analyzer.detectors.god_class  # noqa: F401
import code_analyzer.analyzer.detectors.coupling  # noqa: F401
import code_analyzer.analyzer.detectors.dependency_inversion  # noqa: F401
import code_analyzer.analyzer.detectors.cohesion  # noqa: F401
import code_analyzer.analyzer.detectors.open_closed  # noqa: F401
import code_analyzer.analyzer.detectors.layer_separation  # noqa: F401
import code_analyzer.analyzer.detectors.design_patterns  # noqa: F401
import code_analyzer.analyzer.detectors.circular_deps  # noqa: F401
import code_analyzer.analyzer.detectors.interface_segregation  # noqa: F401
import code_analyzer.analyzer.detectors.bare_except  # noqa: F401
import code_analyzer.analyzer.detectors.none_comparison  # noqa: F401
import code_analyzer.analyzer.detectors.mutable_defaults  # noqa: F401
import code_analyzer.analyzer.detectors.shadowing_builtins  # noqa: F401
import code_analyzer.analyzer.detectors.security  # noqa: F401
import code_analyzer.analyzer.detectors.async_sync_mismatch  # noqa: F401
import code_analyzer.analyzer.detectors.redundant_if_return  # noqa: F401
import code_analyzer.analyzer.detectors.inconsistent_returns  # noqa: F401
import code_analyzer.analyzer.detectors.dot_keys  # noqa: F401
import code_analyzer.analyzer.detectors.string_concat_in_loop  # noqa: F401
import code_analyzer.analyzer.detectors.any_all_list_comp  # noqa: F401
import code_analyzer.analyzer.detectors.deep_nesting  # noqa: F401
import code_analyzer.analyzer.detectors.type_isinstance  # noqa: F401
import code_analyzer.analyzer.detectors.unused_iteration_var  # noqa: F401
import code_analyzer.analyzer.detectors.dict_get  # noqa: F401
import code_analyzer.analyzer.detectors.manual_accumulate  # noqa: F401
import code_analyzer.analyzer.detectors.range_len_loop  # noqa: F401
import code_analyzer.analyzer.detectors.unused_variable  # noqa: F401
import code_analyzer.analyzer.detectors.many_parameters  # noqa: F401
import code_analyzer.analyzer.detectors.wildcard_import  # noqa: F401
import code_analyzer.analyzer.detectors.print_leak  # noqa: F401
import code_analyzer.analyzer.detectors.missing_super_init  # noqa: F401
import code_analyzer.analyzer.detectors.override_signature  # noqa: F401
import code_analyzer.analyzer.detectors.abstract_method  # noqa: F401
import code_analyzer.analyzer.detectors.import_exists  # noqa: F401
import code_analyzer.analyzer.detectors.api_exists  # noqa: F401
import code_analyzer.analyzer.detectors.semantic_duplication  # noqa: F401

from code_analyzer.analyzer.detectors import REGISTRY


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
