"""for i in range(len(...)) anti-pattern detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class RangeLenLoopDetector(Detector):
    default_confidence = 0.9
    name = "RangeLenLoop"
    severity = "MEDIA"
    description = "RangeLenLoop - for i in range(len(x)) should iterate directly over the collection"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.For):
            if not isinstance(node.iter, ast.Call):
                continue
            if not (isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"):
                continue
            if not node.iter.args or not isinstance(node.iter.args[0], ast.Call):
                continue
            call = node.iter.args[0]
            if not (isinstance(call.func, ast.Name) and call.func.id == "len"):
                continue
            target_id = node.target.id if isinstance(node.target, ast.Name) else None
            if target_id is None:
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {node.lineno}",
                line=node.lineno,
                severity="MEDIA",
                issue=f"Loop 'for {target_id} in range(len(...))' should iterate directly over the collection.",
                suggestion="Iterate directly over the collection: 'for item in collection:' instead of accessing by index.",
                line_content=ctx.get_line(node.lineno),
            ))

        return findings
