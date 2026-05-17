"""print() inside non-main functions (debug leak) detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_ALLOWED_FUNCTIONS = {"main", "run", "setup"}


@register
class PrintLeakDetector(Detector):
    name = "PrintLeak"
    severity = "MEDIA"
    description = "PrintLeak - print() inside library functions may be forgotten debug output"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        parents = {child: n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "print":
                continue
            func_name = None
            cur = node
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_name = cur.name
                    break
            if func_name is None or func_name in _ALLOWED_FUNCTIONS:
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {node.lineno}",
                line=node.lineno,
                severity="MEDIA",
                issue=f"print() inside '{func_name}()' may be forgotten debug output left in production.",
                suggestion=f"Replace print() with logging or remove if it was temporary debug output in '{func_name}'.",
                line_content=ctx.get_line(node.lineno),
            ))

        return findings
