"""from module import * wildcard import detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class WildcardImportDetector(Detector):
    name = "WildcardImport"
    severity = "ALTA"
    description = "WildcardImport - 'from x import *' pollutes the namespace and hides dependencies"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names[0].name == "*":
                module = node.module or ""
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="ALTA",
                    issue=f"from {module} import * — wildcard import pollutes the namespace.",
                    suggestion=f"Replace with 'import {module}' or explicit imports: 'from {module} import X, Y, Z'.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
