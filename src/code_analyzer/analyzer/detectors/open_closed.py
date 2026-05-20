"""Open/Closed Principle detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _count_if_chain(if_node: ast.If) -> int:
    count = 1
    current = if_node
    while len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
        count += 1
        current = current.orelse[0]
    return count


@register
class OCPDetector(Detector):
    name = "OCP"
    severity = "MEDIA"
    description = "Open/Closed Principle - open for extension, closed for modification"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for child in func.body:
                if isinstance(child, ast.If):
                    chain = _count_if_chain(child)
                    if chain >= 3:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {child.lineno}",
                            line=child.lineno,
                            severity="MEDIA",
                            issue=(
                                f"Cadeia if/elif com {chain} ramificacoes em '{func.name}'. "
                                "Isso costuma dificultar extensao sem modificar o codigo existente."
                            ),
                            suggestion=(
                                "Considere Strategy, tabela de dispatch ou polimorfismo "
                                "para reduzir a necessidade de alterar a funcao."
                            ),
                            line_content=ctx.get_line(child.lineno),
                        ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
