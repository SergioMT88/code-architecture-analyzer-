"""Bare except detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _enclosing_function(node: ast.AST, code: str) -> str:
    try:
        tree = ast.parse(code)
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(n):
                    if child is node:
                        return n.name
    except SyntaxError:
        pass
    return ""


@register
class BareExceptDetector(Detector):
    name = "BareExcept"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "Bare except - except without type catches SystemExit, KeyboardInterrupt and hides real errors"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                func_name = _enclosing_function(node, ctx.code)
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
