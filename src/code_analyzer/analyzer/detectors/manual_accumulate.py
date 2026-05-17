"""Manual accumulation loop replaceable by comprehension detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class ManualAccumulateDetector(Detector):
    name = "ManualAccumulate"
    severity = "MEDIA"
    description = "ManualAccumulate - for loop with single .append()/.add() should use a comprehension"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            if isinstance(node.target, ast.Name) and node.target.id == "_":
                continue
            if len(node.body) != 1:
                continue
            if not isinstance(node.body[0], ast.Expr):
                continue
            call = node.body[0].value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr not in ("append", "add"):
                continue
            if not isinstance(call.func.value, ast.Name):
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {node.lineno}",
                line=node.lineno,
                severity="MEDIA",
                issue=f"'{call.func.value.id}.{call.func.attr}()' inside loop can be replaced by a comprehension.",
                suggestion="Use a list comprehension or set comprehension instead of manually accumulating in a loop.",
                line_content=ctx.get_line(node.lineno),
            ))

        return findings
