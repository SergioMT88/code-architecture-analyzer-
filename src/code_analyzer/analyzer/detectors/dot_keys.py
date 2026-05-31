"""Unnecessary .keys() call detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class DotKeysDetector(Detector):
    default_confidence = 0.85
    name = "DotKeys"
    severity = "BAIXA"
    description = "DotKeys - unnecessary .keys() in 'in' or 'for'; dict already iterates over keys"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.Compare, ast.For):
            if isinstance(node, ast.Compare):
                for op, comp in zip(node.ops, node.comparators):
                    if not isinstance(op, ast.In):
                        continue
                    if not (isinstance(comp, ast.Call) and isinstance(comp.func, ast.Attribute) and comp.func.attr == "keys"):
                        continue
                    var = comp.func.value.id if isinstance(comp.func.value, ast.Name) else "d"
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="BAIXA",
                        issue=".keys() desnecessario em comparacao 'in'.",
                        suggestion=f"Use 'if x in {var}' em vez de 'if x in {var}.keys()'.",
                        line_content=ctx.get_line(node.lineno),
                    ))
            if isinstance(node, ast.For):
                if not (isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute) and node.iter.func.attr == "keys"):
                    continue
                var = node.iter.func.value.id if isinstance(node.iter.func.value, ast.Name) else "d"
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="BAIXA",
                    issue=".keys() desnecessario em loop 'for'.",
                    suggestion=f"Use 'for k in {var}' em vez de 'for k in {var}.keys()'.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
