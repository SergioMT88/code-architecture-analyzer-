"""IdentityComparison detector — 'is'/'is not' with non-None literals."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class IdentityComparisonDetector(Detector):
    name = "IdentityComparison"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "Identity comparison with non-None literal — 'is' checks object identity, not value equality"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        for node in ctx.get_nodes_by_type(ast.Compare):
            for op, comparator in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Is, ast.IsNot)):
                    continue
                if not isinstance(comparator, ast.Constant):
                    continue
                if comparator.value is None:
                    continue
                op_name = "is not" if isinstance(op, ast.IsNot) else "is"
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="ALTA",
                    issue=(
                        f"Comparacao de identidade '{op_name}' usada com literal "
                        f"{comparator.value!r}. 'is'/'is not' verificam identidade de objeto "
                        "em memoria, nao igualdade de valor — comportamento indefinido com "
                        "strings e ints nao-interned."
                    ),
                    suggestion=f"Substitua '{op_name}' por '==' ou '!=' para comparar valores.",
                    line_content=ctx.get_line(node.lineno),
                ))
        return findings
