"""Redundant if/return True/False detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class RedundantIfReturnDetector(Detector):
    name = "RedundantIfReturn"
    severity = "BAIXA"
    description = "Redundant if/return - if x: return True else: return False can be return x"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.If):
            if len(node.body) == 1 and len(node.orelse) == 1:
                body = node.body[0]
                orelse = node.orelse[0]
                if (
                    isinstance(body, ast.Return) and isinstance(body.value, ast.Constant)
                    and isinstance(orelse, ast.Return) and isinstance(orelse.value, ast.Constant)
                ):
                    b_val = body.value.value
                    o_val = orelse.value.value
                    if b_val is True and o_val is False:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {node.lineno}",
                            line=node.lineno,
                            severity="BAIXA",
                            issue="if/return True/False redundante - pode ser substituido por 'return cond'.",
                            suggestion="Substitua por 'return <condicao>'.",
                            line_content=ctx.get_line(node.lineno),
                        ))
                    elif b_val is False and o_val is True:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {node.lineno}",
                            line=node.lineno,
                            severity="BAIXA",
                            issue="if/return False/True redundante - pode ser substituido por 'return not cond'.",
                            suggestion="Substitua por 'return not <condicao>'.",
                            line_content=ctx.get_line(node.lineno),
                        ))

        return findings
