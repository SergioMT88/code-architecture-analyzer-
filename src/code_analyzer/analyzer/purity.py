"""Purity classifier — labels dataflow candidate blocks as pure/side_effect/unknown."""
from __future__ import annotations

import ast
from typing import Any, Dict, List

_SIDE_EFFECT_CALLS = frozenset({
    "open", "print", "write", "read", "close", "send", "recv",
    "execute", "commit", "rollback", "save", "delete", "create",
    "update", "insert", "filter", "get", "all", "first", "last",
    "request", "get", "post", "put", "patch",
    "sleep", "exit", "abort", "raise_exception",
})

_ORM_ATTRS = frozenset({
    "objects", "save", "delete", "create", "update", "filter",
    "get", "all", "first", "last", "bulk_create", "bulk_update",
    "select_related", "prefetch_related", "annotate", "aggregate",
})


def classify_block(
    func_node: ast.FunctionDef,
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """Classify a dataflow candidate block as pure, side_effect, or unknown.

    Walks AST nodes whose lineno falls within [start_line, end_line].
    Returns {"purity": str, "reasons": [str]}.
    """
    start = candidate["start_line"]
    end = candidate["end_line"]

    reasons: List[str] = []
    purity = "pure"

    candidate_stmts = [
        stmt for stmt in ast.walk(func_node)
        if hasattr(stmt, "lineno") and start <= stmt.lineno <= end
    ]

    for node in candidate_stmts:
        # self.* attribute access
        if isinstance(node, ast.Attribute):
            val = node.value
            if isinstance(val, ast.Name) and val.id == "self":
                reasons.append(f"acessa self.{node.attr}")
                purity = "side_effect"
                continue
            # ORM pattern: queryset.filter(), .save(), etc.
            if node.attr in _ORM_ATTRS:
                reasons.append(f"ORM: .{node.attr}()")
                purity = "side_effect"
                continue

        # global / nonlocal
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            names = getattr(node, "names", [])
            reasons.append(f"acesso nao-local: {', '.join(names)}")
            purity = "side_effect"
            continue

        # function calls
        if isinstance(node, ast.Call):
            func = node.func
            call_name = None
            if isinstance(func, ast.Name):
                call_name = func.id
            elif isinstance(func, ast.Attribute):
                call_name = func.attr

            if call_name in _SIDE_EFFECT_CALLS:
                reasons.append(f"chamada I/O: {call_name}()")
                purity = "side_effect"
                continue

            # unresolvable call (not a simple Name or known Attribute) → unknown
            if call_name is None and purity == "pure":
                reasons.append("chamada nao resolvivel")
                purity = "unknown"

    return {"purity": purity, "reasons": reasons}


def classify_file(
    tree: ast.Module,
    dataflow_results: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Classify all dataflow candidates across the file.

    Returns {func_name: [{start_line, end_line, purity, reasons}]}.
    """
    func_nodes: Dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_nodes[node.name] = node  # type: ignore[assignment]

    result: Dict[str, List[Dict[str, Any]]] = {}
    for func_result in dataflow_results:
        func_name = func_result["function"]
        func_node = func_nodes.get(func_name)
        if func_node is None:
            continue
        classified: List[Dict[str, Any]] = []
        for candidate in func_result.get("candidates", []):
            info = classify_block(func_node, candidate)
            classified.append({
                "start_line": candidate["start_line"],
                "end_line": candidate["end_line"],
                "span": candidate["span"],
                "variables": candidate.get("variables", []),
                "suggested_name": candidate.get("suggested_name", "_extract"),
                "purity": info["purity"],
                "reasons": info["reasons"],
            })
        if classified:
            result[func_name] = classified
    return result
