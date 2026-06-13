"""Public API for the code_analyzer.analyzer package."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.analyzer.detection_runner import detect_all as detect_all

_log = logging.getLogger(__name__)


def run_analysis(filepath: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a full architecture analysis on *filepath* and return the result dict."""
    from code_analyzer.analyzer.core import ArchitectureAnalyzer, run_ruff
    from code_analyzer.project_context import load_project_context

    file_path = Path(filepath)
    if not file_path.exists():
        return {"success": False, "error": f"Arquivo nao encontrado: {filepath}"}
    try:
        code = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"success": False, "error": f"Erro ao ler arquivo: {exc}"}

    analyzer = ArchitectureAnalyzer(code, filepath, config=config)
    result = analyzer.analyze()

    if result.get("success"):
        result["config"] = config or {}
        ruff_result = run_ruff(filepath)
        result["tool_findings"] = {
            "ruff": ruff_result["findings"],
            "total": len(ruff_result["findings"]),
        }
        warnings: List[str] = []
        if not ruff_result["available"]:
            warnings.append("ruff nao instalado — analise parcial")
        if warnings:
            result["tool_warnings"] = warnings

        result["project_context"] = load_project_context(filepath)

        # µ2: purity classification of dataflow candidates
        tree = result.pop("tree", None)  # remove non-serializable AST node from result
        if tree is not None:
            try:
                from code_analyzer.analyzer.dataflow import analyze_file as _df_analyze
                from code_analyzer.analyzer.purity import classify_file as _classify_file
                df_results = _df_analyze(tree)
                result["dataflow_results"] = df_results
                result["purity_map"] = _classify_file(tree, df_results)
            except Exception:  # dataflow/purity analysis may fail unpredictably
                _log.warning("Dataflow/purity analysis failed for %s", filepath, exc_info=True)
                result["dataflow_results"] = []
                result["purity_map"] = {}

            # µ3: single-file taint (informational — never affects the score).
            # Own try/except so a taint failure doesn't drop dataflow above.
            result["taint_findings"] = []
            if "TaintFlow" not in (config or {}).get("ignore_criteria", []):
                try:
                    from code_analyzer.analyzer.taint_tracker import analyze_file_taint
                    result["taint_findings"] = analyze_file_taint(
                        tree, filepath, code.splitlines()
                    )
                except Exception:  # taint analysis may fail unpredictably
                    _log.warning("Taint analysis failed for %s", filepath, exc_info=True)
                    result["taint_findings"] = []

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
