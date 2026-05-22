"""Coupling detector — checks import count and inline imports."""
from __future__ import annotations

import ast
import logging
from typing import TYPE_CHECKING, List

_log = logging.getLogger(__name__)

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import build_parent_map, STDLIB_MODULES

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _is_inside_try_except(node: ast.AST, parent_map: dict) -> bool:
    curr_key = id(node)
    while curr_key in parent_map:
        parent = parent_map[curr_key]
        if isinstance(parent, (ast.Try, ast.ExceptHandler)):
            return True
        curr_key = id(parent)
    return False


def _detect_inline_imports(ctx: "AnalysisContext") -> List[dict]:
    inline = []
    try:
        tree = ctx.tree
        parent_map = build_parent_map(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)) and child != node:
                        if _is_inside_try_except(child, parent_map):
                            continue
                        module = ""
                        if isinstance(child, ast.Import):
                            module = child.names[0].name
                        elif isinstance(child, ast.ImportFrom):
                            module = child.module or ""
                        inline.append({
                            "lineno": child.lineno,
                            "module": module,
                            "inside_function": node.name,
                            "line_content": ctx.get_line(child.lineno),
                        })
    except Exception:
        _log.debug("Inline import detection failed for %s", ctx.filepath, exc_info=True)
        pass
    return inline


@register
class CouplingDetector(Detector):
    name = "Coupling"
    severity = "ALTA"
    description = "Coupling - degree of interdependence between modules"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        max_imports = ctx.threshold("max_imports", 20)
        
        # Filtrar apenas os imports externos/locais únicos que não são da stdlib
        external_imports = set()
        for imp in ctx.imports:
            if not imp:
                continue
            if imp.startswith('.'):
                external_imports.add(imp)
                continue
            parts = imp.split('.')
            root = parts[0]
            if root not in STDLIB_MODULES:
                external_imports.add(imp)

        n_imports = len(external_imports)
        n_classes = max(1, len(ctx.classes))
        findings: List[Finding] = []

        if n_imports > max_imports:
            findings.append(Finding(
                criterion=self.name,
                location="imports (topo do arquivo)",
                line=1,
                severity="ALTA",
                issue=(
                    f"O arquivo possui {n_imports} imports externos/locais unicos, acima do limite configurado {max_imports}."
                ),
                suggestion="Revise dependencias, remova imports nao usados e considere separar responsabilidades.",
            ))
        if n_imports > n_classes * 4:
            findings.append(Finding(
                criterion=self.name,
                location="imports (topo do arquivo)",
                line=1,
                severity="ALTA",
                issue=f"Alto acoplamento: {n_imports} modulos externos importados para {n_classes} classe(s).",
                suggestion="Use Dependency Injection ou Facade para reduzir dependencias diretas.",
            ))

        for imp in _detect_inline_imports(ctx):
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {imp['lineno']}",
                line=imp["lineno"],
                severity="MEDIA",
                issue=f"Import '{imp['module']}' dentro da funcao '{imp['inside_function']}' - mova para o topo",
                suggestion=f"Mova 'import {imp['module']}' para o topo do arquivo.",
                line_content=imp["line_content"],
            ))

        return findings
