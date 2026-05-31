"""Shadowing builtins detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_BUILTINS = {
    "list", "dict", "set", "tuple", "int", "str", "float", "bool",
    "id", "type", "len", "max", "min", "sum", "any", "all",
    "map", "filter", "zip", "sorted", "reversed", "iter", "next",
    "input", "print", "open", "file", "dir", "vars", "object",
}


@register
class ShadowingBuiltinsDetector(Detector):
    default_confidence = 0.9
    name = "ShadowingBuiltins"
    severity = "MEDIA"
    description = "Shadowing builtins - names like list, dict, id, type used as variable or parameter"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.FunctionDef, ast.AsyncFunctionDef, ast.Name):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.arg in _BUILTINS:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {arg.lineno}",
                            line=arg.lineno,
                            severity="MEDIA",
                            issue=f"Parametro '{arg.arg}' em '{node.name}()' sombra o builtin '{arg.arg}'.",
                            suggestion=f"Renomeie o parametro '{arg.arg}' para evitar confusao com o builtin.",
                            line_content=ctx.get_line(arg.lineno),
                        ))
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id in _BUILTINS:
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="MEDIA",
                        issue=f"Variavel '{node.id}' sombra o builtin '{node.id}'.",
                        suggestion=f"Renomeie a variavel '{node.id}' para evitar confusao com o builtin.",
                        line_content=ctx.get_line(node.lineno),
                    ))

        return findings
