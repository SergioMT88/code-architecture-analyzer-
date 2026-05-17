#!/usr/bin/env python3
"""
Refactorer v2.1.4 - Refatoracoes estruturais com AST + dry-run + backup.

Transformacoes aplicadas (todas seguras e nao-destrutivas):
- Adiciona docstring de modulo (se ausente)
- Remove imports duplicados
- Remove imports nao usados (deteccao via AST)
- Converte f-strings sem placeholders em strings normais
- Renomeia variaveis ambiguas (l, I, O) em comprehensions
"""

import ast
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from artifact_manager import ArtifactRegistry


AMBIGUOUS_NAMES = {"l", "I", "O"}
AMBIGUOUS_REPLACEMENTS = {"l": "ln", "I": "idx", "O": "obj"}


class RefactoringOrchestrator:
    """Orquestra refatoracao em 5 micro-fases com suporte a dry-run."""

    def __init__(
        self,
        filepath: str,
        dry_run: bool = False,
        output_dir: Optional[str] = None,
        structured_outputs: bool = True,
        artifact_registry: Optional[ArtifactRegistry] = None,
        quiet: bool = False,
    ):
        self.filepath = Path(filepath)
        self.dry_run = dry_run
        self.original_code = self.filepath.read_text(encoding='utf-8')
        self.code = self.original_code
        self.backup_path: Optional[Path] = None
        self.changes: List[Dict] = []
        self.quiet = quiet
        self.artifacts = artifact_registry or ArtifactRegistry(
            self.filepath,
            output_dir=output_dir,
            structured_outputs=structured_outputs,
        )

    def phase1_setup(self) -> Dict[str, Any]:
        """Micro-fase 1: Setup/Preparacao."""
        if not self.quiet:
            print("  Phase 1: Setup/Preparation...")

        if self.dry_run:
            return {
                "status": "dry-run",
                "message": "DRY-RUN: backup seria criado mas nao foi aplicado",
                "original_size": len(self.original_code),
                "backup_target": str(self.artifacts.path_for("backup", f"{self.filepath.stem}_backup.py")),
            }

        self.backup_path = self.artifacts.path_for("backup", f"{self.filepath.stem}_backup.py")
        shutil.copy(self.filepath, self.backup_path)
        self.artifacts.record(
            "backup",
            self.backup_path,
            description="Backup automático antes da refatoração",
        )

        return {
            "status": "success",
            "backup_created": str(self.backup_path),
            "original_size": len(self.original_code)
        }

    def _add_module_docstring(self, code: str, changes: List[Dict]) -> str:
        """Adiciona docstring se nao houver shebang e nem docstring existente."""
        first_line = code.lstrip().split('\n')[0] if code else ""
        has_shebang = first_line.startswith('#!')
        stripped = code.lstrip()
        has_docstring = stripped.startswith('"""') or stripped.startswith("'''")

        if has_shebang or has_docstring:
            return code

        new_code = '"""\nModulo refatorado - adicione descricao aqui.\n"""\n\n' + code
        changes.append({
            "type": "docstring",
            "description": "Docstring de modulo adicionada (estava ausente)",
            "before": "(sem docstring)",
            "after": '"""\nModulo refatorado - adicione descricao aqui.\n"""'
        })
        return new_code

    def _remove_duplicate_imports(self, code: str, changes: List[Dict]) -> str:
        """Remove imports duplicados linha-a-linha."""
        lines = code.split('\n')
        seen: Set[str] = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                if stripped not in seen:
                    seen.add(stripped)
                    new_lines.append(line)
                else:
                    changes.append({
                        "type": "duplicate_import",
                        "description": f"Import duplicado removido: {stripped}",
                        "before": line,
                        "after": "(removido)"
                    })
            else:
                new_lines.append(line)
        return '\n'.join(new_lines)

    def _remove_unused_imports(self, code: str, changes: List[Dict]) -> str:
        """Remove imports nao usados (deteccao via AST)."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        imported: Dict[int, List[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = []
                for alias in node.names:
                    names.append(alias.asname or alias.name.split('.')[0])
                imported[node.lineno] = names
            elif isinstance(node, ast.ImportFrom):
                names = []
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    names.append(alias.asname or alias.name)
                imported[node.lineno] = names

        used_names: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                cur = node
                while isinstance(cur, ast.Attribute):
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    used_names.add(cur.id)

        unused_lines: Set[int] = set()
        manual_cleanup: List[Dict[str, Any]] = []
        for lineno, names in imported.items():
            used = [name for name in names if name in used_names or name == "__future__"]
            if not used:
                unused_lines.add(lineno)
            elif len(used) != len(names):
                manual_cleanup.append({
                    "type": "partial_unused_import",
                    "description": (
                        f"Import na linha {lineno} tem nomes usados e nao usados; "
                        "a limpeza automatica foi pulada para evitar perda de alias"
                    ),
                    "before": code.split('\n')[lineno - 1],
                    "after": "(manter e revisar manualmente)",
                })

        if not unused_lines:
            changes.extend(manual_cleanup)
            return code

        lines = code.split('\n')
        kept = []
        for i, line in enumerate(lines, start=1):
            if i in unused_lines:
                changes.append({
                    "type": "unused_import",
                    "description": f"Import nao usado removido (linha {i})",
                    "before": line,
                    "after": "(removido)"
                })
                continue
            kept.append(line)
        changes.extend(manual_cleanup)
        return '\n'.join(kept)

    def _fix_useless_fstrings(self, code: str, changes: List[Dict]) -> str:
        """Converte f-strings sem placeholders ({}) em strings normais (F541)."""
        new_tokens = []

        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.STRING and token.string[:1] in ("f", "F"):
                try:
                    expr = ast.parse(token.string, mode="eval").body
                except SyntaxError:
                    expr = None

                if isinstance(expr, ast.JoinedStr) and all(
                    isinstance(value, ast.Constant) for value in expr.values
                ):
                    literal_value = "".join(
                        "" if value.value is None else str(value.value)
                        for value in expr.values
                    )
                    replacement = repr(literal_value)
                    changes.append({
                        "type": "useless_fstring",
                        "description": "f-string sem placeholders convertida para string normal",
                        "before": token.string,
                        "after": replacement
                    })
                    token = tokenize.TokenInfo(
                        token.type,
                        replacement,
                        token.start,
                        token.end,
                        token.line,
                    )
            new_tokens.append(token)

        return tokenize.untokenize(new_tokens)

    def _rename_ambiguous_vars(self, code: str, changes: List[Dict]) -> str:
        """Renomeia variaveis ambiguas (l, I, O) em list/dict/set comprehensions (E741)."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        substitutions: List[Tuple[int, str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for gen in node.generators:
                    target = gen.target
                    if isinstance(target, ast.Name) and target.id in AMBIGUOUS_NAMES:
                        new_name = AMBIGUOUS_REPLACEMENTS[target.id]
                        substitutions.append((target.lineno, target.id, new_name))

        if not substitutions:
            return code

        new_code = code
        for lineno, old, new in substitutions:
            pattern = re.compile(rf"\b{re.escape(old)}\b")
            lines = new_code.split('\n')
            if lineno - 1 < len(lines):
                lines[lineno - 1] = pattern.sub(new, lines[lineno - 1])
                new_code = '\n'.join(lines)
                changes.append({
                    "type": "ambiguous_variable",
                    "description": f"Variavel ambigua '{old}' renomeada para '{new}' (linha {lineno})",
                    "before": f"variavel '{old}'",
                    "after": f"variavel '{new}'"
                })

        return new_code

    def phase2_refactor_structure(self) -> Dict[str, Any]:
        """Micro-fase 2: Refatoracao Estrutural (cleanup seguro)."""
        if not self.quiet:
            print("  Phase 2: Structural Refactoring...")

        changes: List[Dict] = []
        working = self.code

        working = self._add_module_docstring(working, changes)
        working = self._remove_duplicate_imports(working, changes)
        working = self._remove_unused_imports(working, changes)
        working = self._fix_useless_fstrings(working, changes)
        working = self._rename_ambiguous_vars(working, changes)

        if not self.dry_run:
            self.code = working

        self.changes.extend(changes)
        return {
            "status": "dry-run" if self.dry_run else "success",
            "changes_found": len(changes),
            "changes_detail": changes
        }

    def phase3_tests(self) -> Dict[str, Any]:
        """Micro-fase 3: Scaffold de Testes Unitarios."""
        if not self.quiet:
            print("  Phase 3: Unit Tests...")

        test_file = self.artifacts.path_for("test", f"test_{self.filepath.stem}.py")

        if test_file.exists():
            return {
                "status": "skipped",
                "message": f"Arquivo de testes ja existe: {test_file.name}"
            }

        header = (
            f'"""Tests for {self.filepath.name}'
            f' - generated by Code Architecture Analyzer v2.1.4"""'
        )
        test_methods = self._generate_test_methods()
        methods_block = "\n\n".join(test_methods) if test_methods else ""
        test_content = (
            f"{header}\n"
            f"\n"
            f"import pytest\n"
            f"from {self.filepath.stem} import {self._get_importable_names()}\n"
            f"\n"
            f"\n"
            f"class Test{self.filepath.stem.capitalize().replace('_', '')}:\n"
            f'    """Test suite for {self.filepath.stem}"""\n'
            f"\n"
            f"{methods_block}\n"
            f"\n"
            f'if __name__ == "__main__":\n'
            f'    pytest.main([__file__, "-v"])\n'
        )
        if not self.dry_run:
            test_file.write_text(test_content, encoding='utf-8')
            self.artifacts.record(
                "test",
                test_file,
                description="Scaffold de testes pytest gerado automaticamente",
            )
            return {"status": "success", "test_file_created": str(test_file)}
        else:
            return {
                "status": "dry-run",
                "message": f"DRY-RUN: criaria {test_file.name}",
                "preview": test_content[:200] + "..."
            }

    def _get_importable_names(self) -> str:
        """Extrai nomes de funcoes e classes do codigo fonte para import."""
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return ""
        names = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    names.append(node.name)
            elif isinstance(node, ast.ClassDef):
                names.append(node.name)
        return ", ".join(names)

    def _generate_default_arg(self, arg: ast.arg) -> str:
        """Gera um valor dummy para um parametro baseado na dica de tipo."""
        if arg.annotation is None:
            return "None"
        annotation = arg.annotation
        if isinstance(annotation, ast.Name):
            name = annotation.id
            if name in ("int", "float"):
                return "0"
            if name in ("str",):
                return '""'
            if name in ("bool",):
                return "False"
            if name in ("list", "List"):
                return "[]"
            if name in ("dict", "Dict"):
                return "{}"
            if name in ("tuple", "Tuple"):
                return "()"
            if name in ("set", "Set"):
                return "set()"
            if name in ("Optional",):
                return "None"
            return "None"
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                if annotation.value.id in ("list", "List", "dict", "Dict"):
                    return "None"
        return "None"

    def _generate_test_methods(self) -> List[str]:
        """Gera metodos de teste com assertions reais baseados nas funcoes."""
        methods = []
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return [self._make_placeholder()]
        funcs = [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        if not funcs:
            return [self._make_placeholder()]
        for func in funcs:
            methods.append(self._make_test_for_func(func))
        return methods

    def _make_placeholder(self) -> str:
        return ('    def test_module_imports(self):\n'
                '        """Verify module imports without errors."""\n'
                '        assert True')

    def _make_test_for_func(self, func: ast.FunctionDef) -> str:
        is_async = isinstance(func, ast.AsyncFunctionDef)
        func_name = func.name
        has_return = self._has_return(func)

        args = []
        defaults = func.args.defaults
        num_no_default = len(func.args.args) - len(defaults)
        for i, arg in enumerate(func.args.args):
            if arg.arg in ("self", "cls", "mcs"):
                continue
            default_idx = i - num_no_default
            if default_idx >= 0:
                default_ast = defaults[default_idx]
                args.append(self._ast_to_dummy(default_ast))
            else:
                args.append(self._generate_default_arg(arg))
        arg_str = ", ".join(args)

        if is_async:
            call = f"await {func_name}({arg_str})" if arg_str else f"await {func_name}()"
            header = "@pytest.mark.asyncio\n"
        else:
            call = f"{func_name}({arg_str})" if arg_str else f"{func_name}()"
            header = ""

        if has_return:
            body = f"result = {call}\nassert result is not None"
        else:
            body = f"{call}\nassert True"

        indent = "        "
        indented_body = indent + body.replace("\n", "\n" + indent)
        return (
            f'{header}'
            f'    def test_{func_name}(self):\n'
            f'        """Test {func_name}."""\n'
            f'{indented_body}')

    def _has_return(self, node: ast.AST) -> bool:
        """Verifica se uma funcao tem pelo menos um return com valor."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Return) and child.value is not None:
                return True
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if self._has_return(child):
                return True
        return False

    def _ast_to_dummy(self, node: ast.AST) -> str:
        """Converte um no AST de valor padrao para string Python."""
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.List):
            return "[]"
        if isinstance(node, ast.Dict):
            return "{}"
        if isinstance(node, ast.Tuple):
            return "()"
        if isinstance(node, ast.Set):
            return "set()"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.Constant):
                return repr(-node.operand.value)
        if isinstance(node, ast.Name):
            if node.id == "None":
                return "None"
            if node.id in ("True", "False"):
                return node.id
        return "None"

    def phase4_formatting(self) -> Dict[str, Any]:
        """Micro-fase 4: Formatacao."""
        if not self.quiet:
            print("  Phase 4: Formatting...")

        result: Dict[str, Any] = {"status": "success", "tools_used": []}

        if not self.dry_run and shutil.which("black"):
            try:
                with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as tmp:
                    tmp.write(self.code)
                    tmp_path = Path(tmp.name)
                proc = subprocess.run(
                    ["black", str(tmp_path), "--quiet"],
                    capture_output=True, text=True, timeout=15
                )
                if proc.returncode == 0:
                    self.code = tmp_path.read_text(encoding='utf-8')
                    result["tools_used"].append("black")
                tmp_path.unlink(missing_ok=True)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        if not self.dry_run and shutil.which("isort"):
            try:
                with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as tmp:
                    tmp.write(self.code)
                    tmp_path = Path(tmp.name)
                proc = subprocess.run(
                    ["isort", str(tmp_path), "--quiet"],
                    capture_output=True, text=True, timeout=15
                )
                if proc.returncode == 0:
                    self.code = tmp_path.read_text(encoding='utf-8')
                    result["tools_used"].append("isort")
                tmp_path.unlink(missing_ok=True)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        if not result["tools_used"]:
            lines = self.code.split('\n')
            lines = [line.rstrip() for line in lines]
            cleaned = []
            prev_blank = False
            for line in lines:
                if not line.strip():
                    if not prev_blank:
                        cleaned.append(line)
                    prev_blank = True
                else:
                    cleaned.append(line)
                    prev_blank = False
            if not self.dry_run:
                self.code = '\n'.join(cleaned)
            result["tools_used"].append("basic-formatter")

        return result

    def phase5_validation(self) -> Dict[str, Any]:
        """Micro-fase 5: Validacao Final."""
        if not self.quiet:
            print("  Phase 5: Final Validation...")

        try:
            compile(self.code, str(self.filepath), 'exec')
            syntax_valid = True
            error = None
        except SyntaxError as e:
            syntax_valid = False
            error = f"Linha {e.lineno}: {e.msg}"

        return {
            "status": "success" if syntax_valid else "failed",
            "syntax_valid": syntax_valid,
            "error": error,
            "final_lines": len(self.code.split('\n'))
        }

    def generate_diff(self) -> str:
        """Gera diff entre codigo original e refatorado."""
        if self.original_code == self.code:
            return "Sem alteracoes."

        orig_lines = self.original_code.split('\n')
        new_lines = self.code.split('\n')

        diff_lines = []
        max_lines = max(len(orig_lines), len(new_lines))
        changes = 0

        for i in range(max_lines):
            orig = orig_lines[i] if i < len(orig_lines) else ""
            new = new_lines[i] if i < len(new_lines) else ""
            if orig != new:
                diff_lines.append(f"- Linha {i+1}: {orig}")
                diff_lines.append(f"+ Linha {i+1}: {new}")
                changes += 1
                if changes >= 10:
                    diff_lines.append("... (mais alteracoes omitidas)")
                    break

        return "\n".join(diff_lines) if diff_lines else "Sem alteracoes detectadas."

    def execute_refactoring(self) -> Dict[str, Any]:
        """Executa todas as 5 micro-fases."""
        mode = "DRY-RUN" if self.dry_run else "APLICANDO"
        if self.quiet:
            print(f"\nIMPLEMENTATION [{mode}]")
        else:
            print(f"\n{'='*60}")
            print(f"IMPLEMENTATION (5 MICRO-PHASES) [{mode}]")
            print('='*60 + '\n')

        results: Dict[str, Any] = {"phases": {}, "dry_run": self.dry_run}

        results["phases"]["1_setup"] = self.phase1_setup()
        results["phases"]["2_refactor"] = self.phase2_refactor_structure()
        results["phases"]["3_tests"] = self.phase3_tests()
        results["phases"]["4_formatting"] = self.phase4_formatting()
        results["phases"]["5_validation"] = self.phase5_validation()

        results["diff"] = self.generate_diff()
        results["total_changes"] = len(self.changes)

        if not results["phases"]["5_validation"]["syntax_valid"]:
            results["error"] = (
                "Refatoracao abortada porque a validacao final detectou erro de sintaxe"
            )
            manifest_path = self.artifacts.save_manifest(
                {
                    "mode": mode,
                    "changes_found": len(self.changes),
                    "validation": results["phases"]["5_validation"],
                    "error": results["error"],
                }
            )
            results["manifest"] = str(manifest_path)
            if not self.quiet:
                print("\nREFACTORING ABORTED - validacao final falhou.\n")
            return results

        if not self.dry_run:
            self.filepath.write_text(self.code, encoding='utf-8')
            results["refactored_file"] = str(self.filepath)
            results["backup_file"] = str(self.backup_path)
            diff_path = self.artifacts.path_for("refactor", f"{self.filepath.stem}_diff.txt")
            diff_path.write_text(self.generate_diff(), encoding="utf-8")
            self.artifacts.record(
                "refactor",
                diff_path,
                description="Diff resumido da refatoração aplicada",
            )
            if not self.quiet:
                print("\nREFACTORING COMPLETED!\n")
        else:
            if not self.quiet:
                print("\nDRY-RUN COMPLETE - nenhum arquivo foi modificado.\n")
                print("Use sem --dry-run para aplicar as alteracoes.\n")

        manifest_path = self.artifacts.save_manifest(
            {
                "mode": mode,
                "changes_found": len(self.changes),
                "validation": results["phases"]["5_validation"],
            }
        )
        results["manifest"] = str(manifest_path)

        return results


def refactor_file(
    filepath: str,
    dry_run: bool = False,
    output_dir: Optional[str] = None,
    structured_outputs: bool = True,
    artifact_registry: Optional[ArtifactRegistry] = None,
    quiet: bool = False,
) -> Dict[str, Any]:
    try:
        orchestrator = RefactoringOrchestrator(
            filepath,
            dry_run=dry_run,
            output_dir=output_dir,
            structured_outputs=structured_outputs,
            artifact_registry=artifact_registry,
            quiet=quiet,
        )
        return orchestrator.execute_refactoring()
    except Exception as e:
        return {"error": f"Erro: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python refactorer.py <arquivo.py> [--dry-run]")
        sys.exit(1)

    is_dry_run = "--dry-run" in sys.argv
    is_json = "--json" in sys.argv
    is_quiet = "--quiet" in sys.argv or is_json
    result = refactor_file(sys.argv[1], dry_run=is_dry_run, quiet=is_quiet)
    if is_json:
        print(json.dumps(result, ensure_ascii=True, default=str))
    else:
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
