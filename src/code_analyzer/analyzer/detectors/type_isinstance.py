"""type(x) == T instead of isinstance detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class TypeIsInstanceDetector(Detector):
    default_confidence = 0.85
    name = "TypeIsInstance"
    severity = "BAIXA"
    description = "TypeIsInstance - type(x) == T does not support inheritance; use isinstance(x, T)"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
                    continue
                if not (
                    isinstance(node.left, ast.Call)
                    and isinstance(node.left.func, ast.Name)
                    and node.left.func.id == "type"
                    and node.left.args
                ):
                    continue
                type_name = ""
                if isinstance(comp, ast.Name):
                    type_name = comp.id
                elif isinstance(comp, ast.Tuple):
                    type_name = ", ".join(e.id for e in comp.elts if isinstance(e, ast.Name))
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="BAIXA",
                    issue=f"type(...) == {type_name} nao suporta heranca.",
                    suggestion=f"Use isinstance(x, {type_name}) para suportar subclasses.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
