"""ContextManagerLeak detector — open() called without 'with' statement."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_RESOURCE_FUNCS = frozenset({"open"})


def _has_with_ancestor(node: ast.AST, parent_map: dict) -> bool:
    cur = parent_map.get(node)
    while cur is not None:
        if isinstance(cur, ast.With):
            return True
        cur = parent_map.get(cur)
    return False


@register
class ContextManagerLeakDetector(Detector):
    name = "ContextManagerLeak"
    severity = "MEDIA"
    penalty_per_finding = 2
    default_confidence = 0.8
    description = "Context manager leak — open() used without 'with' statement; file may not be closed on exception"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        reported: Set[int] = set()
        parent_map = ctx.parents

        for node in ctx.get_nodes_by_type(ast.Call):
            func = node.func
            # open(...) as bare Name
            if isinstance(func, ast.Name) and func.id in _RESOURCE_FUNCS:
                if _has_with_ancestor(node, parent_map):
                    continue
                lineno = node.lineno
                if lineno in reported:
                    continue
                reported.add(lineno)
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {lineno}",
                    line=lineno,
                    severity="MEDIA",
                    issue=(
                        "open() chamado sem 'with' statement. Se ocorrer uma excecao antes de f.close(), "
                        "o arquivo fica aberto indefinidamente, causando resource leak."
                    ),
                    suggestion=(
                        "Use 'with open(...) as f:' para garantir fechamento automatico mesmo em caso de excecao."
                    ),
                    line_content=ctx.get_line(lineno),
                ))

        return findings
