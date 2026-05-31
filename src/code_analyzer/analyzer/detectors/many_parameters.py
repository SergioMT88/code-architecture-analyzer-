"""Function with too many parameters detector (>6)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class ManyParametersDetector(Detector):
    default_confidence = 0.8
    name = "ManyParameters"
    severity = "MEDIA"
    description = "ManyParameters - functions with more than 6 parameters are hard to call and test"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.FunctionDef, ast.AsyncFunctionDef):
            params = node.args.args + node.args.kwonlyargs
            if node.args.vararg:
                params.append(node.args.vararg)
            if node.args.kwarg:
                params.append(node.args.kwarg)
            if node.args.posonlyargs:
                params = node.args.posonlyargs + params
            if len(params) > 6:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="MEDIA",
                    issue=f"Function '{node.name}' has {len(params)} parameters (recommended max: 6).",
                    suggestion=f"Group related parameters into a config object or split '{node.name}' into smaller functions.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
