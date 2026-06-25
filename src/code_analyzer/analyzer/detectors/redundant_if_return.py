"""Redundant if/return True/False detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _is_boolean_expression(test: ast.expr) -> bool:
    """Check if an expression is provably boolean.

    Returns True for Compare nodes (x > y, x == y, etc.) which are always
    boolean in Python. Other expressions (Names, Attributes, Calls) may be
    truthy/falsy but not boolean, so wrapping in bool() is required.
    """
    return isinstance(test, ast.Compare)


@register
class RedundantIfReturnDetector(Detector):
    default_confidence = 0.8
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
                    is_bool = _is_boolean_expression(node.test)
                    if b_val is True and o_val is False:
                        suggestion = "return <condicao>" if is_bool else "return bool(<condicao>)"
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {node.lineno}",
                            line=node.lineno,
                            severity="BAIXA",
                            issue="if/return True/False redundante - pode ser substituido por 'return cond'.",
                            suggestion=f"Substitua por '{suggestion}'.",
                            line_content=ctx.get_line(node.lineno),
                        ))
                    elif b_val is False and o_val is True:
                        suggestion = "return not <condicao>" if is_bool else "return not bool(<condicao>)"
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {node.lineno}",
                            line=node.lineno,
                            severity="BAIXA",
                            issue="if/return False/True redundante - pode ser substituido por 'return not cond'.",
                            suggestion=f"Substitua por '{suggestion}'.",
                            line_content=ctx.get_line(node.lineno),
                        ))

        return findings
