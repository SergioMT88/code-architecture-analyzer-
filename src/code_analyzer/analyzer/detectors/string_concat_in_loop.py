"""String concatenation inside loop detector (O(n^2) pattern)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class StringConcatInLoopDetector(Detector):
    name = "StringConcatInLoop"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "StringConcatInLoop - s += x inside loop is O(n^2); prefer list + ''.join()"

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
            loop_var = node.target.id if isinstance(node.target, ast.Name) else None

            for child in ast.walk(node):
                if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                    if isinstance(child.target, ast.Name) and child.target.id != loop_var:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {child.lineno}",
                            line=child.lineno,
                            severity="ALTA",
                            issue=f"'{child.target.id} += ...' dentro de loop pode ser lento com strings (O(n^2)).",
                            suggestion="Acumule partes em uma lista e use '\"\".join(partes)' no final.",
                            line_content=ctx.get_line(child.lineno),
                        ))
                elif (
                    isinstance(child, ast.Assign)
                    and len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Name)
                    and isinstance(child.value, ast.BinOp)
                    and isinstance(child.value.op, ast.Add)
                    and isinstance(child.value.left, ast.Name)
                    and child.value.left.id == child.targets[0].id
                    and child.targets[0].id != loop_var
                ):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {child.lineno}",
                        line=child.lineno,
                        severity="ALTA",
                        issue=f"'{child.targets[0].id} = {child.targets[0].id} + ...' dentro de loop pode ser lento (O(n^2)).",
                        suggestion="Acumule partes em uma lista e use '\"\".join(partes)' no final.",
                        line_content=ctx.get_line(child.lineno),
                    ))

        return findings
