"""None comparison detector (== None / != None)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class NoneComparisonDetector(Detector):
    name = "NoneComparison"
    severity = "MEDIA"
    penalty_per_finding = 3
    description = "None comparison using ==/!= - use 'is None' / 'is not None'"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.Compare):
            has_none = any(
                isinstance(c, ast.Constant) and c.value is None
                for c in [node.left] + node.comparators
            )
            if not has_none:
                continue
            for op in node.ops:
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    op_name = "==" if isinstance(op, ast.Eq) else "!="
                    replacement = "is not None" if isinstance(op, ast.NotEq) else "is None"
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="MEDIA",
                        issue=(
                            f"Comparacao com None usando '{op_name}'. "
                            "Isso pode dar falsos positivos com objetos que implementam __eq__."
                        ),
                        suggestion=f"Substitua '{op_name} None' por '{replacement}'.",
                        line_content=ctx.get_line(node.lineno),
                    ))

        return findings
