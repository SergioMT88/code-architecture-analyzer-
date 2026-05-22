"""Layer Separation detector."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_INFRA_MODULES = {"flask", "fastapi", "django", "requests", "sqlite3", "sqlalchemy"}


@register
class LayerSeparationDetector(Detector):
    name = "LayerSeparation"
    severity = "ALTA"
    description = "Layer Separation - UI, business logic, and data access should be in separate modules"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        io_calls = []
        infrastructure_modules: set = set()
        for node in ctx.get_nodes_by_type(ast.Call, ast.Import, ast.ImportFrom):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"print", "input", "open"}:
                    io_calls.append(node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base in _INFRA_MODULES:
                        infrastructure_modules.add(base)
            elif isinstance(node, ast.ImportFrom):
                base = (node.module or "").split(".")[0]
                if base in _INFRA_MODULES:
                    infrastructure_modules.add(base)

        if io_calls and (ctx.classes or ctx.functions):
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {min(io_calls)}",
                line=min(io_calls),
                severity="ALTA",
                issue=(
                    "O arquivo mistura chamadas de I/O com logica de dominio. "
                    "Isso dificulta teste, manutencao e reuso."
                ),
                suggestion=(
                    "Separe camada de apresentacao/CLI, servico de negocio e acesso a dados "
                    "em modulos distintos."
                ),
                line_content=ctx.get_line(min(io_calls)),
            ))

        if infrastructure_modules and (ctx.classes or ctx.functions):
            findings.append(Finding(
                criterion=self.name,
                location="imports do topo",
                line=1,
                severity="MEDIA",
                issue=(
                    f"O arquivo depende de modulos de infraestrutura ({', '.join(sorted(infrastructure_modules))}) "
                    "e ainda concentra logica de negocio. A separacao de camadas pode estar fraca."
                ),
                suggestion="Isolar infraestrutura em adaptadores ou repositorios e manter a regra de negocio independente.",
            ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
