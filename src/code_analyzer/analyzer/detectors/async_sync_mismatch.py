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
    default_confidence = 0.9
    description = "Async/sync mismatch - async without await or await outside async"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.AsyncFunctionDef):
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

        parents = ctx.parents
        for node in ctx.get_nodes_by_type(ast.Await):
            cur = parents.get(node)
            while cur is not None:
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
                cur = parents.get(cur)

        return findings
