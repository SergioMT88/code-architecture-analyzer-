"""ImportExists detector — checks if imported modules are installed or exist in the environment."""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors.coupling import STDLIB_MODULES

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _module_exists(module_name: str, search_path: str | None = None) -> bool:
    """Check if a module exists in the Python environment using find_spec safely."""
    # Extrai o primeiro componente do import (ex: "pandas" de "pandas.core")
    root_module = module_name.split(".")[0]
    if not root_module:
        return False
    if root_module in STDLIB_MODULES:
        return True

    sys_path_added = False
    if search_path and search_path not in sys.path:
        sys.path.insert(0, search_path)
        sys_path_added = True

    try:
        spec = importlib.util.find_spec(root_module)
        return spec is not None
    except Exception:
        # Fail-safe: considera que existe para evitar falsos positivos
        return True
    finally:
        if sys_path_added and search_path:
            try:
                sys.path.remove(search_path)
            except ValueError:
                pass


@register
class ImportExistsDetector(Detector):
    name = "ImportExists"
    severity = "ALTA"
    description = "ImportExists - Checks if imported modules are installed or exist in the project"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        # Determinar o diretório pai para resolver imports locais
        search_path = None
        if ctx.filepath:
            search_path = str(Path(ctx.filepath).parent.resolve())

        # Encontrar todas as declarações de importação e suas linhas no AST
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not _module_exists(module_name, search_path):
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {node.lineno}",
                            line=node.lineno,
                            severity="ALTA",
                            issue=f"Modulo '{module_name}' nao esta instalado no ambiente ou nao foi encontrado.",
                            suggestion=f"Instale '{module_name}' usando pip ou adicione-o as dependencias do projeto.",
                            line_content=ctx.get_line(node.lineno),
                        ))
            elif isinstance(node, ast.ImportFrom):
                # Se for import relativo (level > 0), assume-se válido localmente
                if node.level > 0:
                    continue
                module_name = node.module or ""
                if not module_name:
                    continue
                if not _module_exists(module_name, search_path):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=f"Modulo '{module_name}' nao esta instalado no ambiente ou nao foi encontrado.",
                        suggestion=f"Instale '{module_name}' usando pip ou adicione-o as dependencias do projeto.",
                        line_content=ctx.get_line(node.lineno),
                    ))

        return findings
