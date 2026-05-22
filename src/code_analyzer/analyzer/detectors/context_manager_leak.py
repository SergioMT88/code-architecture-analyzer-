"""ContextManagerLeak detector — open() called without 'with' statement."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import build_parent_map

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_RESOURCE_FUNCS = frozenset({"open"})


def _has_with_ancestor(node: ast.AST, parent_map: dict) -> bool:
    node_id = id(node)
    while node_id in parent_map:
        parent = parent_map[node_id]
        if isinstance(parent, ast.With):
            return True
        node_id = id(parent)
    return False


@register
class ContextManagerLeakDetector(Detector):
    name = "ContextManagerLeak"
    severity = "MEDIA"
    penalty_per_finding = 2
    description = "Context manager leak — open() used without 'with' statement; file may not be closed on exception"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        reported: Set[int] = set()
        parent_map = build_parent_map(ctx.tree)

        for node in ast.walk(ctx.tree):
            if not isinstance(node, ast.Call):
                continue
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
