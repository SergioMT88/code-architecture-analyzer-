"""Data-flow analysis — identifies extractable variable clusters in long functions."""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Set

_BUILTINS = frozenset({
    "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
    "print", "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "sum", "min", "max", "abs", "round", "isinstance", "issubclass", "hasattr",
    "getattr", "setattr", "type", "repr", "None", "True", "False",
    "self", "cls", "args", "kwargs",
})

MIN_FUNC_LINES = 50
MIN_CLUSTER_LINES = 10
MIN_CLUSTER_VARS = 2


def _collect_stmt_defuse(stmts: list) -> List[Dict[str, Any]]:
    """Return def/use sets for each top-level statement in a function body."""
    result = []
    for stmt in stmts:
        defs: Set[str] = set()
        uses: Set[str] = set()
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                name = node.id
                if name in _BUILTINS or len(name) <= 1:
                    continue
                if isinstance(node.ctx, ast.Store):
                    defs.add(name)
                elif isinstance(node.ctx, ast.Load):
                    uses.add(name)
        result.append({
            "lineno": stmt.lineno,
            "end_lineno": getattr(stmt, "end_lineno", stmt.lineno),
            "defs": defs,
            "uses": uses,
        })
    return result


def _find_clusters(stmts: List[Dict[str, Any]], exclude: Set[str] | None = None) -> List[List[int]]:
    """Group statement indices into connected components via shared variables (BFS).

    Variables in *exclude* (e.g. function parameters) are ignored so they don't
    artificially connect otherwise independent clusters.
    """
    _exclude = exclude or set()
    var_index: Dict[str, List[int]] = {}
    for i, stmt in enumerate(stmts):
        for var in (stmt["defs"] | stmt["uses"]) - _exclude:
            var_index.setdefault(var, []).append(i)

    visited = [False] * len(stmts)
    clusters: List[List[int]] = []

    for start in range(len(stmts)):
        if visited[start]:
            continue
        group: List[int] = []
        queue = [start]
        while queue:
            idx = queue.pop(0)
            if visited[idx]:
                continue
            visited[idx] = True
            group.append(idx)
            for var in stmts[idx]["defs"] | stmts[idx]["uses"]:
                for neighbor in var_index.get(var, []):
                    if not visited[neighbor]:
                        queue.append(neighbor)
        clusters.append(sorted(group))

    return clusters


def _suggest_name(local_defs: Set[str]) -> str:
    """Heuristically derive an extraction name from the cluster's defined variables."""
    candidates = sorted(v for v in local_defs if not v.startswith("_"))[:2]
    if not candidates:
        candidates = sorted(local_defs)[:1]
    return "_" + "_".join(candidates) if candidates else "_extract"


def _get_params(func_node: ast.FunctionDef) -> Set[str]:
    """Return the set of parameter names for a function."""
    params: Set[str] = set()
    for arg in func_node.args.args + func_node.args.posonlyargs + func_node.args.kwonlyargs:
        params.add(arg.arg)
    if func_node.args.vararg:
        params.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        params.add(func_node.args.kwarg.arg)
    return params


def analyze_function(func_node: ast.FunctionDef) -> List[Dict[str, Any]]:
    """Find extractable clusters in a single function. Returns up to 3 candidates."""
    func_end = getattr(func_node, "end_lineno", func_node.lineno)
    if func_end - func_node.lineno < MIN_FUNC_LINES:
        return []

    # Exclude parameters — they are external and would connect unrelated clusters
    params = _get_params(func_node)

    stmts = _collect_stmt_defuse(func_node.body)
    if len(stmts) < 4:
        return []

    clusters = _find_clusters(stmts, exclude=params)
    candidates: List[Dict[str, Any]] = []

    for group in clusters:
        if len(group) < 2:
            continue
        start_line = stmts[group[0]]["lineno"]
        end_line = stmts[group[-1]]["end_lineno"]
        span = end_line - start_line

        if span < MIN_CLUSTER_LINES:
            continue
        if start_line <= func_node.lineno + 1 and end_line >= func_end - 1:
            continue

        local_defs: Set[str] = set()
        all_vars: Set[str] = set()
        for idx in group:
            local_defs |= stmts[idx]["defs"]
            all_vars |= stmts[idx]["defs"] | stmts[idx]["uses"]

        if len(local_defs) < MIN_CLUSTER_VARS:
            continue

        candidates.append({
            "start_line": start_line,
            "end_line": end_line,
            "span": span,
            "variables": sorted(local_defs),
            "suggested_name": _suggest_name(local_defs),
        })

    candidates.sort(key=lambda c: c["span"], reverse=True)
    return candidates[:3]


def analyze_file(tree: ast.Module) -> List[Dict[str, Any]]:
    """Find extractable clusters across all long functions in a parsed file."""
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        candidates = analyze_function(node)
        if candidates:
            results.append({
                "function": node.name,
                "function_line": node.lineno,
                "function_end": getattr(node, "end_lineno", node.lineno),
                "candidates": candidates,
            })
    return results
