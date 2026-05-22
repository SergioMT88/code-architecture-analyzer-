"""any([...])/all([...]) with list comprehension detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class AnyAllListCompDetector(Detector):
    name = "AnyAllListComp"
    severity = "MEDIA"
    description = "AnyAllListComp - any([...])/all([...]) creates unnecessary intermediate list; use generator"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in ("any", "all")):
                continue
            if not node.args or not isinstance(node.args[0], ast.ListComp):
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {node.lineno}",
                line=node.lineno,
                severity="MEDIA",
                issue=f"{node.func.id}([comprehension]) cria lista intermediaria desnecessaria.",
                suggestion=f"Remova os colchetes: '{node.func.id}(x for x in ...)'.",
                line_content=ctx.get_line(node.lineno),
            ))

        return findings
