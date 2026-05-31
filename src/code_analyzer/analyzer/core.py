"""Slim ArchitectureAnalyzer — AST visitor + metrics only, no detector logic."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.analyzer.detection_runner import detect_all
from code_analyzer.analyzer.context import AnalysisContext
from code_analyzer.analyzer.criteria_cache import get_cached_criteria, save_criteria
from code_analyzer.analyzer.detectors.circular_deps import _build_graph, _find_cycles
from code_analyzer.analyzer.detectors.coupling import _detect_inline_imports
from code_analyzer.analyzer.detectors._utils import STDLIB_MODULES
from code_analyzer.analyzer.scoring import maintainability_index, mi_grade
from code_analyzer.config import DEFAULT_CONFIG as _DEFAULT_CONFIG
from code_analyzer.constants import (
    COUPLING_MAX_UNIQUE_IMPORTS,
    COUPLING_PENALTY_UNIQUE,
    COUPLING_MAX_THIRD_PARTY,
    COUPLING_PENALTY_THIRD_PARTY,
    COUPLING_STARTING_SCORE,
)
from code_analyzer.limits import MAX_MISSING_TESTS_LIST, MAX_TOOL_FINDINGS
from code_analyzer import __version__ as _ANALYZER_VERSION

def _agents_md_hash(filepath: str) -> str:
    """Return a short hash of AGENTS.md content, or '' if not found."""
    from code_analyzer.agents_rules import find_agents_md
    agents = find_agents_md(Path(filepath))
    if agents is None:
        return ""
    try:
        content = agents.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]
    except OSError:
        return ""


_STDLIB = {
    "os", "sys", "json", "re", "math", "datetime", "pathlib",
    "typing", "collections", "itertools", "functools", "abc",
    "io", "time", "copy", "shutil", "subprocess", "threading",
    "asyncio", "logging", "unittest", "dataclasses", "enum",
}


class ArchitectureAnalyzer(ast.NodeVisitor):
    """Visits a Python AST to collect classes, functions, and imports for analysis."""

    def __init__(
        self,
        code: str,
        filepath: str = "<unknown>",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.filepath = filepath
        self.lines = code.split("\n")
        self.config: Dict[str, Any] = dict(_DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.classes: Dict[str, Any] = {}
        self.functions: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.import_nodes: List[Dict[str, Any]] = []
        self.cyclomatic_complexity: int = 0
        self._current_class: Optional[str] = None
        self._tree: Optional[ast.AST] = None

    # ------------------------------------------------------------------
    # NodeVisitor hooks
    # ------------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        methods = [
            {
                "name": n.name,
                "lineno": n.lineno,
                "complexity": self._calculate_complexity(n),
                "lines": (n.end_lineno or n.lineno) - n.lineno,
                "params": len(n.args.args),
            }
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        lines = (node.end_lineno or 0) - (node.lineno or 0)
        bases = [ast.unparse(b) for b in node.bases] if node.bases else []
        self._current_class = node.name
        self.classes[node.name] = {
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno or node.lineno,
            "methods": methods,
            "num_methods": len(methods),
            "lines": lines,
            "complexity": self._calculate_complexity(node),
            "bases": bases,
            "attributes": self._get_class_attributes(node),
        }
        self.generic_visit(node)
        self._current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._current_class is None:
            cx = self._calculate_complexity(node)
            self.functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "complexity": cx,
                "lines": (node.end_lineno or node.lineno) - node.lineno,
            })
            self.cyclomatic_complexity += cx
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
            self.import_nodes.append(
                {"module": alias.name, "lineno": node.lineno, "type": "import"}
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        self.imports.append(module)
        self.import_nodes.append({
            "module": module,
            "lineno": node.lineno,
            "type": "from",
            "names": [alias.name for alias in node.names],
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_class_attributes(self, node: ast.ClassDef) -> List[str]:
        attrs = []
        for item in ast.walk(node):
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        attrs.append(target.attr)
        return list(set(attrs))

    def _calculate_complexity(self, node: ast.AST) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(
                child,
                (ast.If, ast.For, ast.While, ast.ExceptHandler,
                 ast.With, ast.Assert, ast.comprehension),
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _get_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    # ------------------------------------------------------------------
    # Analysis entry point
    # ------------------------------------------------------------------

    def analyze(self) -> Dict[str, Any]:
        try:
            tree = ast.parse(self.code)
            self._tree = tree
            self.visit(tree)
        except SyntaxError as e:
            return {"success": False, "error": f"Erro de sintaxe na linha {e.lineno}: {e.msg}"}

        ctx = AnalysisContext(
            code=self.code,
            lines=self.lines,
            filepath=self.filepath,
            classes=self.classes,
            functions=self.functions,
            imports=self.imports,
            import_nodes=self.import_nodes,
            config=self.config,
            tree=tree,
        )

        agents_md_hash = _agents_md_hash(self.filepath)
        cached = get_cached_criteria(self.code, self.config, _ANALYZER_VERSION, agents_md_hash)
        if cached is not None:
            criteria = cached
            timings = []
            cache_hit = True
        else:
            criteria = self._apply_llm_aware_heuristics(detect_all(ctx))
            save_criteria(self.code, self.config, _ANALYZER_VERSION, criteria, agents_md_hash)
            timings = getattr(ctx, "_detector_timings", [])
            cache_hit = False
        return {
            "success": True,
            "tree": tree,
            "metrics": self._calculate_metrics(),
            "classes": self.classes,
            "functions": self.functions,
            "imports": self.import_nodes,
            "criteria": criteria,
            "dependencies": self._analyze_dependencies(ctx),
            "test_analysis": self._analyze_tests(),
            "performance": {
                "cache_hit": cache_hit,
                "detector_timings": sorted(
                    [{"name": n, "seconds": round(s, 4)} for n, s in timings],
                    key=lambda x: x["seconds"],
                    reverse=True,
                ),
                "total_detection_seconds": round(sum(s for _, s in timings), 4),
            },
        }

    def _apply_llm_aware_heuristics(self, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """If 3+ classic LLM-generated patterns are violated, elevate severity."""
        llm_patterns = ["BareExcept", "MutableDefault", "PrintLeak", "UnusedVariable"]
        violated = [p for p in llm_patterns if criteria.get(p, {}).get("findings")]
        if len(violated) >= 3:
            for name, crit in criteria.items():
                findings = crit.get("findings", [])
                if findings and crit.get("severity") == "MEDIA":
                    crit["severity"] = "ALTA"
                    crit["description"] = crit.get("description", "") + " (LLM-Aware: elevado para ALTA)"
                    for f in findings:
                        if f.get("severity") == "MEDIA":
                            f["severity"] = "ALTA"
        return criteria

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _calculate_metrics(self) -> Dict[str, Any]:
        code_lines = [ln for ln in self.lines if ln.strip() and not ln.strip().startswith("#")]
        comment_lines = [ln for ln in self.lines if ln.strip().startswith("#")]
        all_methods = [m for cls in self.classes.values() for m in cls["methods"]]
        complexities = (
            [m["complexity"] for m in all_methods]
            + [f["complexity"] for f in self.functions]
        )
        total_cx = sum(complexities)
        mi = maintainability_index(
            self.lines, total_cx, max(1, len(complexities)),
            tree=self._tree,
        )
        comment_ratio = round(len(comment_lines) / max(1, len(code_lines)) * 100, 1)
        target_ratio = int(self.config.get("min_comment_ratio", 10))
        return {
            "lines_of_code": len(self.lines),
            "code_lines": len(code_lines),
            "comment_lines": len(comment_lines),
            "blank_lines": len([ln for ln in self.lines if not ln.strip()]),
            "num_classes": len(self.classes),
            "num_functions": len(self.functions),
            "num_imports": len(set(self.imports)),
            "avg_cyclomatic_complexity": round(
                sum(complexities) / max(1, len(complexities)), 2
            ),
            "max_cyclomatic_complexity": max(complexities) if complexities else 0,
            "maintainability_index": mi,
            "maintainability_grade": mi_grade(mi),
            "comment_ratio": comment_ratio,
            "comment_ratio_target": target_ratio,
            "comment_ratio_ok": comment_ratio >= target_ratio,
            "comment_ratio_gap": round(max(0, target_ratio - comment_ratio), 1),
        }

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def _analyze_dependencies(self, ctx: AnalysisContext) -> Dict[str, Any]:
        import_names = [n["module"] for n in self.import_nodes]
        third_party = [m for m in import_names if m.split(".")[0] not in _STDLIB and m]
        internal = [m for m in import_names if m.startswith(".")]

        seen: set = set()
        duplicate_imports = []
        for node in self.import_nodes:
            key = node["module"]
            if key in seen:
                duplicate_imports.append({
                    "module": key,
                    "lineno": node["lineno"],
                    "issue": f"Module '{key}' imported multiple times",
                    "line_content": self._get_line(node["lineno"]),
                })
            seen.add(key)

        inline = _detect_inline_imports(ctx)

        try:
            info = _build_graph(self.filepath)
            cycles = [list(c) for c in _find_cycles(info["graph"])]
        except Exception:
            cycles = []

        unique = len(seen)
        coupling_score = COUPLING_STARTING_SCORE
        coupling_issues = []
        if unique > COUPLING_MAX_UNIQUE_IMPORTS:
            coupling_score -= COUPLING_PENALTY_UNIQUE
            coupling_issues.append(f"{unique} imported modules (> {COUPLING_MAX_UNIQUE_IMPORTS}) — high coupling")
        if len(third_party) > COUPLING_MAX_THIRD_PARTY:
            coupling_score -= COUPLING_PENALTY_THIRD_PARTY
            coupling_issues.append(f"{len(third_party)} external dependencies (> {COUPLING_MAX_THIRD_PARTY})")

        return {
            "total_imports": len(self.import_nodes),
            "unique_modules": unique,
            "third_party": list(set(third_party)),
            "internal": internal,
            "duplicate_imports": duplicate_imports,
            "inline_imports": inline,
            "circular_dependencies": cycles,
            "coupling_score": {"score": max(0, coupling_score), "issues": coupling_issues},
        }

    # ------------------------------------------------------------------
    # Test analysis
    # ------------------------------------------------------------------

    def _analyze_tests(self) -> Dict[str, Any]:
        test_functions = [f for f in self.functions if f["name"].startswith("test_")]
        test_classes = {k: v for k, v in self.classes.items() if k.startswith("Test")}
        total_methods = sum(c["num_methods"] for c in self.classes.values())
        test_methods = sum(v["num_methods"] for v in test_classes.values())
        coverage_estimate = (
            round(min(100, test_methods / total_methods * 100), 1)
            if total_methods > 0
            else 0
        )
        return {
            "test_functions": len(test_functions),
            "test_classes": len(test_classes),
            "has_assertions": "assert " in self.code,
            "uses_pytest": "import pytest" in self.code or "from pytest" in self.code,
            "uses_unittest": "import unittest" in self.code,
            "estimated_coverage": coverage_estimate,
            "missing_tests": self._find_missing_tests(test_classes),
        }

    def _find_missing_tests(self, test_classes: Dict[str, Any]) -> List[str]:
        tested_names = {
            m["name"].replace("test_", "")
            for cls in test_classes.values()
            for m in cls["methods"]
        }
        missing = []
        for cls_name, cls_info in self.classes.items():
            if not cls_name.startswith("Test"):
                for method in cls_info["methods"]:
                    if not method["name"].startswith("_") and method["name"] not in tested_names:
                        missing.append(f"{cls_name}.{method['name']} (linha {method['lineno']})")
        return missing[:MAX_MISSING_TESTS_LIST]


# ------------------------------------------------------------------
# External tool runners
# ------------------------------------------------------------------

_TOOL_AVAILABLE: Dict[str, bool] = {}  # cache de disponibilidade por sessão


def _is_tool_available(tool: str) -> bool:
    if tool not in _TOOL_AVAILABLE:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True, timeout=5)
            _TOOL_AVAILABLE[tool] = True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            _TOOL_AVAILABLE[tool] = False
    return _TOOL_AVAILABLE[tool]


# Ruff ruleset — replaces pylint coverage with native checks at ~25x the speed.
# E,F,W = pycodestyle + pyflakes (default).  B = bugbear (common bugs).
# SIM = simplify.  UP = pyupgrade.  PL = full pylint port (R0902, R0913, PLW1510, etc).
# RUF = ruff-specific rules.  N = pep8-naming (naming conventions: N801-N816).
_RUFF_DEFAULT_SELECT = "E,F,W,B,SIM,UP,PL,RUF,N"


def _severity_for_ruff(code: str) -> str:
    """Map ruff code prefix to severity bucket used in tool_findings."""
    if code.startswith("E") or code.startswith("F") or code.startswith("PLE"):
        return "ALTA"
    if code.startswith("W") or code.startswith("PLW") or code.startswith("B") or code.startswith("N"):
        return "MEDIA"
    return "BAIXA"


def run_ruff(filepath: str) -> Dict[str, Any]:
    """Run ruff if available and return findings + availability flag.

    Uses an expanded ruleset (``_RUFF_DEFAULT_SELECT``) that subsumes the
    pylint checks the project previously relied on.
    """
    result: Dict[str, Any] = {"findings": [], "available": True}
    if not _is_tool_available("ruff"):
        result["available"] = False
        return result
    try:
        proc = subprocess.run(
            [
                "ruff", "check", filepath,
                f"--select={_RUFF_DEFAULT_SELECT}",
                "--output-format=json",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if proc.stdout:
            for item in json.loads(proc.stdout)[:MAX_TOOL_FINDINGS]:
                code = item.get("code", "")
                result["findings"].append({
                    "tool": "ruff",
                    "lineno": item.get("location", {}).get("row", 0),
                    "code": code,
                    "issue": item.get("message", ""),
                    "severity": _severity_for_ruff(code),
                })
    except (subprocess.TimeoutExpired, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return result
