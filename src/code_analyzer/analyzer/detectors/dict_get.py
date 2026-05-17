"""dict[key] without .get() fallback detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class DictGetDetector(Detector):
    name = "DictGet"
    severity = "BAIXA"
    description = "DictGet - dict[key] without .get() may raise KeyError; prefer .get() for optional keys"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        names_with_dot_get: set = set()
        names_with_subscript: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and isinstance(node.func.value, ast.Name):
                    names_with_dot_get.add(node.func.value.id)
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and isinstance(node.ctx, ast.Load):
                    names_with_subscript.add(node.value.id)

        for name in sorted(names_with_subscript):
            if name in names_with_dot_get:
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"references to '{name}'",
                line=0,
                severity="BAIXA",
                issue=f"Access to '{name}[key]' without fallback. If the key may be missing, use .get().",
                suggestion=f"Use '{name}.get(key)' or '{name}.get(key, default)' instead of '{name}[key]'.",
                line_content="",
            ))

        return findings
