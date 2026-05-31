"""ImportExists detector — checks if imported modules are installed or exist in the environment."""
from __future__ import annotations

import ast
import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List

_log = logging.getLogger(__name__)

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors.coupling import STDLIB_MODULES

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _is_local_project_module(module_name: str, search_path: str | None) -> bool:
    """Check if module_name is a local .py file or package in the project."""
    if not search_path:
        return False
    root = Path(search_path)
    parts = module_name.split(".")
    # Walk up at most 6 levels to find project root
    for _ in range(6):
        if (root / "manage.py").exists() or (root / "pyproject.toml").exists() or (root / "setup.py").exists():
            break
        if root.parent == root:
            break
        root = root.parent
    candidate_file = root.joinpath(*parts).with_suffix(".py")
    candidate_pkg = root.joinpath(*parts) / "__init__.py"
    return candidate_file.exists() or candidate_pkg.exists()


def _module_exists(module_name: str, search_path: str | None = None) -> bool:
    """Check if a module exists in the Python environment using find_spec safely."""
    root_module = module_name.split(".")[0]
    if not root_module:
        return False
    if root_module in STDLIB_MODULES:
        return True
    if _is_local_project_module(module_name, search_path):
        return True

    sys_path_added = False
    if search_path and search_path not in sys.path:
        sys.path.insert(0, search_path)
        sys_path_added = True

    try:
        spec = importlib.util.find_spec(root_module)
        return spec is not None
    except Exception:
        _log.debug("Failed to find spec for %s — assuming exists", root_module, exc_info=True)
        return True
    finally:
        if sys_path_added and search_path:
            try:
                sys.path.remove(search_path)
            except ValueError:
                pass


@register
class ImportExistsDetector(Detector):
    default_confidence = 0.85
    name = "ImportExists"
    severity = "ALTA"
    description = "ImportExists - Checks if imported modules are installed or exist in the project"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        search_path = None
        if ctx.filepath:
            search_path = str(Path(ctx.filepath).parent.resolve())

        for node in ctx.get_nodes_by_type(ast.Import, ast.ImportFrom):
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
