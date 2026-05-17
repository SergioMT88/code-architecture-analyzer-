"""Async/sync mismatch detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class AsyncSyncMismatchDetector(Detector):
    name = "AsyncSyncMismatch"
    severity = "MEDIA"
    penalty_per_finding = 3
    description = "Async/sync mismatch - async without await or await outside async"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                has_await = any(isinstance(child, ast.Await) for child in ast.walk(node))
                if not has_await:
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="MEDIA",
                        issue=f"Funcao async '{node.name}' nao usa await - pode ser sync.",
                        suggestion=f"Remova 'async' de '{node.name}' se nao ha operacao assincrona.",
                        line_content=ctx.get_line(node.lineno),
                    ))

        parents = {child: n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Await):
                continue
            cur = node
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, ast.FunctionDef):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=f"await usado fora de funcao async em '{cur.name}'.",
                        suggestion=f"Adicione 'async' antes de 'def' em '{cur.name}'.",
                        line_content=ctx.get_line(node.lineno),
                    ))
                    break
                if isinstance(cur, ast.AsyncFunctionDef):
                    break

        return findings
