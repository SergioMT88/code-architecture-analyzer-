"""Bare except detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _enclosing_function(node: ast.AST, ctx: "AnalysisContext") -> str:
    cur = ctx.parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
        cur = ctx.parents.get(cur)
    return ""


@register
class BareExceptDetector(Detector):
    name = "BareExcept"
    severity = "ALTA"
    penalty_per_finding = 3
    default_confidence = 0.95
    description = "Bare except - except without type catches SystemExit, KeyboardInterrupt and hides real errors"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.ExceptHandler):
            if node.type is None:
                func_name = _enclosing_function(node, ctx)
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="ALTA",
                    issue=(
                        "Except sem tipo detectado. "
                        "Isso captura SystemExit, KeyboardInterrupt e erro interno do Python, "
                        "alem de esconder excecoes reais."
                    ),
                    suggestion=(
                        "Substitua 'except:' por 'except Exception:' ou o tipo esperado"
                        + (f" na funcao '{func_name}'" if func_name else "")
                        + "."
                    ),
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
