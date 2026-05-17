"""Mutable default argument detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class MutableDefaultDetector(Detector):
    name = "MutableDefault"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "Mutable default argument - list/dict/set as default parameter is shared between calls"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for default in node.args.defaults + node.args.kw_defaults:
                if default is None:
                    continue
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {default.lineno}",
                        line=default.lineno,
                        severity="ALTA",
                        issue=(
                            f"Argumento mutavel como default em '{node.name}()'. "
                            "O mesmo objeto e compartilhado entre todas as chamadas."
                        ),
                        suggestion=(
                            f"Substitua por '= None' e use 'if arg is None: arg = []' "
                            f"dentro de '{node.name}'."
                        ),
                        line_content=ctx.get_line(default.lineno),
                    ))

        return findings
