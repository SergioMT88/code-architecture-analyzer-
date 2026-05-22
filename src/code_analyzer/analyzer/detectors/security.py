"""Security detector (eval/exec/pickle/input)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class SecurityDetector(Detector):
    name = "Security"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "Security - eval()/exec()/pickle/input() without validation represent risk"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        dangerous = {"eval", "exec"}

        for node in ctx.get_nodes_by_type(ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in dangerous:
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="ALTA",
                    issue=f"{node.func.id}() detectado - risco de injecao de codigo.",
                    suggestion=f"Substitua {node.func.id}() por alternativas seguras (ast.literal_eval, subprocess, etc).",
                    line_content=ctx.get_line(node.lineno),
                ))
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "load"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "pickle"
            ):
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="ALTA",
                    issue="pickle.load() detectado - risco de execucao arbitraria.",
                    suggestion="Substitua pickle por JSON, YAML ou schema validado se possivel.",
                    line_content=ctx.get_line(node.lineno),
                ))
            elif (
                isinstance(node.func, ast.Name)
                and node.func.id == "input"
                and not node.args  # input() with no argument (no prompt) is a prompt-less call
            ):
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linha {node.lineno}",
                    line=node.lineno,
                    severity="MEDIA",
                    issue="input() sem validacao - risco de injecao se combinado com exec/eval.",
                    suggestion="Valide a entrada do usuario antes de usar.",
                    line_content=ctx.get_line(node.lineno),
                ))

        return findings
