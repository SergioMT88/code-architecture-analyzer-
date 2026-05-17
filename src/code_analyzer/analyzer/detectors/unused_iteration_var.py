"""Unused iteration variable in comprehension detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class UnusedIterationVarDetector(Detector):
    name = "UnusedIterationVar"
    severity = "MEDIA"
    description = "UnusedIterationVar - comprehension iteration variable unused in output expression"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                continue
            if not node.generators:
                continue
            gen = node.generators[0]
            iter_vars: set = set()
            for n in ast.walk(gen.target):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    iter_vars.add(n.id)
            if "_" in iter_vars:
                continue
            used_vars: set = set()
            for n in ast.walk(node.elt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used_vars.add(n.id)
            if iter_vars and not (iter_vars & used_vars):
                vars_str = ", ".join(sorted(iter_vars))
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="MEDIA",
                    issue=f"Comprehension does not use iteration variable '{vars_str}' in its output expression.",
                    suggestion="If the goal is a side effect, use a regular 'for' loop instead of a comprehension.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
