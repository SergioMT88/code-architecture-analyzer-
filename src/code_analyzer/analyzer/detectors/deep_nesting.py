"""Deep nesting detector (>3 levels of for/if/while)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_NESTED = (ast.For, ast.AsyncFor, ast.If, ast.While)


@register
class DeepNestingDetector(Detector):
    name = "DeepNesting"
    severity = "MEDIA"
    penalty_per_finding = 3
    description = "DeepNesting - more than 3 levels of nesting (for/if/while) hurts readability"

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
            if not isinstance(node, _NESTED):
                continue
            depth = 0
            cur = node
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, (ast.Try, ast.ExceptHandler)):
                    break
                if isinstance(cur, _NESTED):
                    depth += 1
            if depth >= 3:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="MEDIA",
                    issue=f"Aninhamento de {depth} niveis de controle (for/if/while). Prejudica legibilidade.",
                    suggestion="Extraia blocos internos para funcoes separadas ou use early returns/continues.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
