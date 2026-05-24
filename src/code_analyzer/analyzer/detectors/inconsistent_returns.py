"""Inconsistent return types detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Optional

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


_BUILTIN_RETURN_TYPES: dict = {
    # bool builtins
    "all": "bool", "any": "bool", "bool": "bool",
    "isinstance": "bool", "issubclass": "bool", "hasattr": "bool", "callable": "bool",
    # int builtins
    "int": "int", "len": "int", "ord": "int", "hash": "int", "id": "int",
    # float builtins (max/min/sum depend on args — treat as float to avoid noise)
    "float": "float", "abs": "float", "round": "float", "max": "float", "min": "float", "sum": "float",
    # str builtins
    "str": "str", "repr": "str", "chr": "str",
    # collection constructors
    "list": "list", "tuple": "tuple", "dict": "dict", "set": "set",
}


def _infer_type(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return "None"
    if isinstance(node, ast.Constant):
        return "None" if node.value is None else type(node.value).__name__
    if isinstance(node, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(node, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(node, (ast.Tuple, ast.GeneratorExp)):
        return "tuple"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        mapped = _BUILTIN_RETURN_TYPES.get(node.func.id)
        if mapped:
            return mapped
        return f"{node.func.id}()"
    return "unknown"


@register
class InconsistentReturnsDetector(Detector):
    name = "InconsistentReturns"
    severity = "MEDIA"
    penalty_per_finding = 3
    description = "Inconsistent returns - different return types across branches of a function"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.FunctionDef, ast.AsyncFunctionDef):
            # Collect Return nodes inside ExceptHandlers — intentional error returns
            except_return_ids: set = set()
            for child in ast.walk(node):
                if isinstance(child, ast.ExceptHandler):
                    for inner in ast.walk(child):
                        if isinstance(inner, ast.Return):
                            except_return_ids.add(id(inner))
            types: set = set()
            for child in ast.walk(node):
                if not isinstance(child, ast.Return):
                    continue
                t = _infer_type(child.value)
                # Skip None returns inside except handlers — standard error-path pattern
                if t == "None" and id(child) in except_return_ids:
                    continue
                types.add(t)
            # Remove implicit None (no return) — functions that return None implicitly
            # alongside explicit returns is standard Python pattern, not a violation
            if "None" in types and len(types) >= 2:
                types.discard("None")
            # If the function has a return type annotation (-> X), trust it.
            # "unknown" just means we couldn't infer the type statically — not a real conflict.
            if node.returns is not None:
                types.discard("unknown")
            # If there is only one known (non-unknown) type, discard "unknown" —
            # a method-call return we can't infer is not evidence of inconsistency.
            known = types - {"unknown"}
            if len(known) == 1:
                types.discard("unknown")
            if len(types) >= 2:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="MEDIA",
                    issue=f"Funcao '{node.name}' retorna tipos diferentes: {', '.join(sorted(types))}.",
                    suggestion=f"Padronize o retorno de '{node.name}' para um unico tipo.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
