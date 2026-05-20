"""ApiExists detector — checks if called module APIs actually exist in the installed modules.

By default only stdlib modules are validated (importing them executes nothing the
interpreter wouldn't already run). To opt into validating third-party modules,
set ``allow_third_party_api_check: true`` in the analyzer config — note that this
imports user-controlled modules, which can execute arbitrary code at import time.
"""
from __future__ import annotations

import ast
import difflib
import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors.coupling import STDLIB_MODULES

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _safe_import_module(module_name: str, search_path: str | None = None) -> Any:
    """Import a module safely, returning the module object or None if it fails."""
    sys_path_added = False
    if search_path and search_path not in sys.path:
        sys.path.insert(0, search_path)
        sys_path_added = True
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None
    finally:
        if sys_path_added and search_path:
            try:
                sys.path.remove(search_path)
            except ValueError:
                pass


def _is_safe_to_import(module_name: str, allow_third_party: bool) -> bool:
    if not module_name:
        return False
    root = module_name.split(".")[0]
    if root in STDLIB_MODULES:
        return True
    return allow_third_party


@register
class ApiExistsDetector(Detector):
    name = "ApiExists"
    severity = "ALTA"
    description = "ApiExists - Checks if called APIs actually exist in the imported modules"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        allow_third_party = bool(ctx.config.get("allow_third_party_api_check", False))
        search_path = None
        if ctx.filepath and allow_third_party:
            search_path = str(Path(ctx.filepath).parent.resolve())

        # Passo 1: Construir a tabela de símbolos de imports
        # local_name -> (module_name, attribute_name_in_module)
        import_syms: Dict[str, Tuple[str, str | None]] = {}
        # Cache para guardar módulos carregados com sucesso
        module_cache: Dict[str, Any] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    import_syms[local_name] = (alias.name, None)
            elif isinstance(node, ast.ImportFrom):
                # Se for relativo (level > 0), não tentamos carregar
                if node.level > 0:
                    continue
                module_name = node.module or ""
                if not module_name:
                    continue
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    import_syms[local_name] = (module_name, alias.name)

        # Helper para carregar e cachear módulo
        def get_cached_module(mod_name: str) -> Any:
            if mod_name in module_cache:
                return module_cache[mod_name]
            if not _is_safe_to_import(mod_name, allow_third_party):
                module_cache[mod_name] = None
                return None
            mod_obj = _safe_import_module(mod_name, search_path)
            module_cache[mod_name] = mod_obj
            return mod_obj

        # Passo 2: Validar as propriedades importadas diretamente em ast.ImportFrom
        # Exemplo: from X import A
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                module_name = node.module or ""
                if not module_name:
                    continue
                mod_obj = get_cached_module(module_name)
                if mod_obj is None:
                    continue  # Módulo não instalado ou indisponível
                
                for alias in node.names:
                    name = alias.name
                    if name == "*":
                        continue
                    if not hasattr(mod_obj, name):
                        valid_attrs = [a for a in dir(mod_obj) if not a.startswith("_")]
                        matches = difflib.get_close_matches(name, valid_attrs, n=3, cutoff=0.6)
                        suggestion = f"Substitua '{name}' por uma das APIs validas."
                        if matches:
                            suggestion = f"Substitua '{name}' por uma das APIs validas: {', '.join(matches)}."
                        
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {node.lineno}",
                            line=node.lineno,
                            severity="ALTA",
                            issue=f"API '{name}' nao existe no modulo '{module_name}'.",
                            suggestion=suggestion,
                            line_content=ctx.get_line(node.lineno),
                        ))

        # Passo 3: Validar acessos a atributos no AST
        # Exemplo: requests.gets
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                local_obj = node.value.id
                if local_obj in import_syms:
                    module_name, parent_attr = import_syms[local_obj]
                    attr_name = node.attr

                    if parent_attr is None:
                        # Exemplo: local_obj é requests (módulo completo), attr_name é gets
                        mod_obj = get_cached_module(module_name)
                        if mod_obj is not None:
                            if not hasattr(mod_obj, attr_name):
                                valid_attrs = [a for a in dir(mod_obj) if not a.startswith("_")]
                                matches = difflib.get_close_matches(attr_name, valid_attrs, n=3, cutoff=0.6)
                                suggestion = f"Substitua '{attr_name}' por uma das APIs validas."
                                if matches:
                                    suggestion = f"Substitua '{attr_name}' por uma das APIs validas: {', '.join(matches)}."

                                findings.append(Finding(
                                    criterion=self.name,
                                    location=f"linha {node.lineno}",
                                    line=node.lineno,
                                    severity="ALTA",
                                    issue=f"API '{attr_name}' nao existe no modulo '{module_name}'.",
                                    suggestion=suggestion,
                                    line_content=ctx.get_line(node.lineno),
                                ))
                    else:
                        # Exemplo: local_obj é o atributo parent_attr importado (ex: de requests import auth; auth.gets)
                        mod_obj = get_cached_module(module_name)
                        if mod_obj is not None and hasattr(mod_obj, parent_attr):
                            sub_obj = getattr(mod_obj, parent_attr)
                            if not hasattr(sub_obj, attr_name):
                                valid_attrs = [a for a in dir(sub_obj) if not a.startswith("_")]
                                matches = difflib.get_close_matches(attr_name, valid_attrs, n=3, cutoff=0.6)
                                suggestion = f"Substitua '{attr_name}' por uma das APIs validas."
                                if matches:
                                    suggestion = f"Substitua '{attr_name}' por uma das APIs validas: {', '.join(matches)}."

                                findings.append(Finding(
                                    criterion=self.name,
                                    location=f"linha {node.lineno}",
                                    line=node.lineno,
                                    severity="ALTA",
                                    issue=f"API '{attr_name}' nao existe no sub-objeto '{module_name}.{parent_attr}'.",
                                    suggestion=suggestion,
                                    line_content=ctx.get_line(node.lineno),
                                ))

        return findings
