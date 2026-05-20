"""Structural refactoring engine — 5 micro-phases with dry-run and backup support.

Transformations applied (all safe and non-destructive):
- Add module docstring if absent
- Remove duplicate imports
- Remove unused imports (AST-based detection)
- Convert f-strings without placeholders to plain strings (F541)
- Rename ambiguous variables (l, I, O) in comprehensions (E741)
"""
from __future__ import annotations

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

from code_analyzer.artifact_manager import ArtifactRegistry


AMBIGUOUS_NAMES = {"l", "I", "O"}
AMBIGUOUS_REPLACEMENTS = {"l": "ln", "I": "idx", "O": "obj"}


class RefactoringOrchestrator:
    """Orchestrates refactoring across 5 micro-phases with dry-run support."""

    def __init__(
        self,
        filepath: str,
        dry_run: bool = False,
        output_dir: Optional[str] = None,
        structured_outputs: bool = True,
        artifact_registry: Optional[ArtifactRegistry] = None,
        quiet: bool = False,
        generate_tests: bool = True,
        enabled_rules: Optional[List[str]] = None,
    ) -> None:
        self.filepath = Path(filepath)
        self.dry_run = dry_run
        self.original_code = self.filepath.read_text(encoding="utf-8")
        self.code = self.original_code
        self.backup_path: Optional[Path] = None
        self.changes: List[Dict[str, Any]] = []
        self.quiet = quiet
        self.generate_tests = generate_tests
        self.enabled_rules = enabled_rules
        self.artifacts = artifact_registry or ArtifactRegistry(
            self.filepath,
            output_dir=output_dir,
            structured_outputs=structured_outputs,
        )

    def phase1_setup(self) -> Dict[str, Any]:
        if not self.quiet:
            print("  Phase 1: Setup/Preparation...")
        if self.dry_run:
            return {
                "status": "dry-run",
                "message": "DRY-RUN: backup seria criado mas nao foi aplicado",
                "original_size": len(self.original_code),
                "backup_target": str(
                    self.artifacts.path_for("backup", f"{self.filepath.stem}_backup.py")
                ),
            }
        self.backup_path = self.artifacts.path_for("backup", f"{self.filepath.stem}_backup.py")
        shutil.copy(self.filepath, self.backup_path)
        self.artifacts.record("backup", self.backup_path, description="Backup automático antes da refatoração")
        return {"status": "success", "backup_created": str(self.backup_path), "original_size": len(self.original_code)}

    def _add_module_docstring(self, code: str, changes: List[Dict[str, Any]]) -> str:
        first_line = code.lstrip().split("\n")[0] if code else ""
        if first_line.startswith("#!"):
            return code
        stripped = code.lstrip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            return code
        new_code = '"""\nModulo refatorado - adicione descricao aqui.\n"""\n\n' + code
        changes.append({
            "type": "docstring",
            "description": "docstring de módulo adicionada na linha 1 porque o arquivo não possuía documentação (PEP 257 recomenda docstrings em todo módulo público)",
            "before": "(sem docstring)",
            "after": '"""\nModulo refatorado - adicione descricao aqui.\n"""',
        })
        return new_code

    def _remove_duplicate_imports(self, code: str, changes: List[Dict[str, Any]]) -> str:
        lines = code.split("\n")
        seen: Dict[str, int] = {}
        new_lines = []
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                if stripped not in seen:
                    seen[stripped] = i
                    new_lines.append(line)
                else:
                    first_line = seen[stripped]
                    changes.append({
                        "type": "duplicate_import",
                        "description": f"import '{stripped[:50]}' removido da linha {i} — duplicata já presente na linha {first_line}",
                        "before": line,
                        "after": "(removido)",
                    })
            else:
                new_lines.append(line)
        return "\n".join(new_lines)

    def _remove_unused_imports(self, code: str, changes: List[Dict[str, Any]]) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        imported: Dict[int, List[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported[node.lineno] = [alias.asname or alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [alias.asname or alias.name for alias in node.names if alias.name != "*"]
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
            used = [n for n in names if n in used_names or n == "__future__"]
            if not used:
                unused_lines.add(lineno)
            elif len(used) != len(names):
                manual_cleanup.append({
                    "type": "partial_unused_import",
                    "description": (
                        f"Import na linha {lineno} tem nomes usados e nao usados; "
                        "limpeza automatica pulada para evitar perda de alias"
                    ),
                    "before": code.split("\n")[lineno - 1],
                    "after": "(manter e revisar manualmente)",
                })

        if not unused_lines:
            changes.extend(manual_cleanup)
            return code

        lines = code.split("\n")
        kept = []
        for i, line in enumerate(lines, start=1):
            if i in unused_lines:
                import_names = ", ".join(imported[i])
                changes.append({
                    "type": "unused_import",
                    "description": f"import '{import_names}' removido da linha {i} — nenhum símbolo usado no código (AST-confirmed)",
                    "before": line,
                    "after": "(removido)",
                })
                continue
            kept.append(line)
        changes.extend(manual_cleanup)
        return "\n".join(kept)

    def _fix_useless_fstrings(self, code: str, changes: List[Dict[str, Any]]) -> str:
        new_tokens = []
        for token in tokenize.generate_tokens(io.StringIO(code).readline):
            if token.type == tokenize.STRING and token.string[:1] in ("f", "F"):
                try:
                    expr = ast.parse(token.string, mode="eval").body
                except SyntaxError:
                    expr = None
                if isinstance(expr, ast.JoinedStr) and all(
                    isinstance(v, ast.Constant) for v in expr.values
                ):
                    literal = "".join("" if v.value is None else str(v.value) for v in expr.values)
                    replacement = repr(literal)
                    short = token.string[:40] + "..." if len(token.string) > 40 else token.string
                    changes.append({
                        "type": "useless_fstring",
                        "description": f"f-string '{short}' convertida para literal na linha {token.start[0]} — sem placeholders (ruff F541: f-string sem interpolação)",
                        "before": token.string,
                        "after": replacement,
                    })
                    token = tokenize.TokenInfo(token.type, replacement, token.start, token.end, token.line)
            new_tokens.append(token)
        return tokenize.untokenize(new_tokens)

    def _rename_ambiguous_vars(self, code: str, changes: List[Dict[str, Any]]) -> str:
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
            lines = new_code.split("\n")
            if lineno - 1 < len(lines):
                lines[lineno - 1] = pattern.sub(new, lines[lineno - 1])
                new_code = "\n".join(lines)
                reason = "confundido com dígito '1'" if old == "l" else "confundido com dígito '0'" if old == "O" else "confundido com dígito '1'"
                changes.append({
                    "type": "ambiguous_variable",
                    "description": f"variável ambígua '{old}' renomeada para '{new}' na linha {lineno} ({reason}; PEP 8 E741: nome ambíguo tipo 'l', 'O', 'I')",
                    "before": f"variavel '{old}'",
                    "after": f"variavel '{new}'",
                })
        return new_code

    def phase2_refactor_structure(self) -> Dict[str, Any]:
        if not self.quiet:
            print("  Phase 2: Structural Refactoring...")
        changes: List[Dict[str, Any]] = []
        working = self.code
        rules = self.enabled_rules
        if rules is None:
            rules = ["docstring", "duplicate_imports", "unused_imports", "useless_fstrings", "ambiguous_vars"]
        if "docstring" in rules:
            working = self._add_module_docstring(working, changes)
        if "duplicate_imports" in rules:
            working = self._remove_duplicate_imports(working, changes)
        if "unused_imports" in rules:
            working = self._remove_unused_imports(working, changes)
        if "useless_fstrings" in rules:
            working = self._fix_useless_fstrings(working, changes)
        if "ambiguous_vars" in rules:
            working = self._rename_ambiguous_vars(working, changes)
        if not self.dry_run:
            self.code = working
        self.changes.extend(changes)
        return {
            "status": "dry-run" if self.dry_run else "success",
            "changes_found": len(changes),
            "changes_detail": changes,
        }

    def phase3_tests(self) -> Dict[str, Any]:
        if not self.quiet:
            print("  Phase 3: Unit Tests...")
        if not self.generate_tests:
            return {"status": "disabled", "message": "Geracao de scaffold de testes desativada."}
        test_file = self.artifacts.path_for("test", f"test_{self.filepath.stem}.py")
        if test_file.exists():
            return {"status": "skipped", "message": f"Arquivo de testes ja existe: {test_file.name}"}
        header = f'"""Tests for {self.filepath.name} - generated by Code Architecture Analyzer v2.1.5"""'
        test_methods = self._generate_test_methods()
        methods_block = "\n\n".join(test_methods) if test_methods else ""
        test_content = (
            f"{header}\n\nimport pytest\n"
            f"from {self.filepath.stem} import {self._get_importable_names()}\n\n\n"
            f"class Test{self.filepath.stem.capitalize().replace('_', '')}:\n"
            f'    """Test suite for {self.filepath.stem}"""\n\n'
            f"{methods_block}\n\n"
            f'if __name__ == "__main__":\n    pytest.main([__file__, "-v"])\n'
        )
        if not self.dry_run:
            test_file.write_text(test_content, encoding="utf-8")
            self.artifacts.record("test", test_file, description="Scaffold de testes pytest gerado automaticamente")
            return {"status": "success", "test_file_created": str(test_file)}
        return {"status": "dry-run", "message": f"DRY-RUN: criaria {test_file.name}", "preview": test_content[:200] + "..."}

    def _get_importable_names(self) -> str:
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return ""
        return ", ".join(
            node.name for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not node.name.startswith("_")
        )

    def _generate_default_arg(self, arg: ast.arg) -> str:
        if arg.annotation is None:
            return "None"
        ann = arg.annotation
        if isinstance(ann, ast.Name):
            return {
                "int": "0", "float": "0", "str": '""', "bool": "False",
                "list": "[]", "List": "[]", "dict": "{}", "Dict": "{}",
                "tuple": "()", "Tuple": "()", "set": "set()", "Set": "set()",
            }.get(ann.id, "None")
        return "None"

    def _generate_test_methods(self) -> List[str]:
        try:
            tree = ast.parse(self.code)
        except SyntaxError:
            return [self._make_placeholder()]
        
        test_methods = []
        
        # Funcoes de nivel de modulo
        funcs = [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        for f in funcs:
            test_methods.append(self._make_test_for_func(f))
            
        # Classes e seus metodos
        classes = [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, ast.ClassDef)
            and not node.name.startswith("_")
        ]
        for cls in classes:
            test_methods.extend(self._make_tests_for_class(cls))
            
        if not test_methods:
            return [self._make_placeholder()]
        return test_methods

    def _make_tests_for_class(self, class_node: ast.ClassDef) -> List[str]:
        methods = [
            node for node in ast.iter_child_nodes(class_node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
            and node.name != "__init__"
        ]
        if not methods:
            return []
            
        # Determinar argumentos do __init__ para instanciar a classe
        init_node = next((node for node in ast.iter_child_nodes(class_node) 
                          if isinstance(node, ast.FunctionDef) and node.name == "__init__"), None)
        init_args = []
        if init_node:
            num_no_default = len(init_node.args.args) - len(init_node.args.defaults)
            for i, arg in enumerate(init_node.args.args):
                if arg.arg in ("self", "cls", "mcs"):
                    continue
                default_idx = i - num_no_default
                if default_idx >= 0:
                    init_args.append(self._ast_to_dummy(init_node.args.defaults[default_idx]))
                else:
                    init_args.append(self._generate_default_arg(arg))
        init_args_str = ", ".join(init_args)
        
        class_tests = []
        for m in methods:
            is_async = isinstance(m, ast.AsyncFunctionDef)
            num_no_default = len(m.args.args) - len(m.args.defaults)
            m_args = []
            for i, arg in enumerate(m.args.args):
                if arg.arg in ("self", "cls", "mcs"):
                    continue
                default_idx = i - num_no_default
                if default_idx >= 0:
                    m_args.append(self._ast_to_dummy(m.args.defaults[default_idx]))
                else:
                    m_args.append(self._generate_default_arg(arg))
            m_args_str = ", ".join(m_args)
            
            prefix = "await " if is_async else ""
            call = f"{prefix}obj.{m.name}({m_args_str})"
            header = "@pytest.mark.asyncio\n" if is_async else ""
            
            instantiation = f"obj = {class_node.name}({init_args_str})"
            if self._has_return(m):
                body = f"{instantiation}\nresult = {call}\nassert result is not None"
            else:
                body = f"{instantiation}\n{call}\nassert True"
                
            indent = "        "
            class_tests.append(
                f"{header}"
                f"    def test_{class_node.name.lower()}_{m.name}(self):\n"
                f'        """Test {class_node.name}.{m.name}."""\n'
                f"{indent}{body.replace(chr(10), chr(10) + indent)}"
            )
        return class_tests


    def _make_placeholder(self) -> str:
        return ('    def test_module_imports(self):\n'
                '        """Verify module imports without errors."""\n'
                '        assert True')

    def _make_test_for_func(self, func: ast.FunctionDef) -> str:
        is_async = isinstance(func, ast.AsyncFunctionDef)
        num_no_default = len(func.args.args) - len(func.args.defaults)
        args = []
        for i, arg in enumerate(func.args.args):
            if arg.arg in ("self", "cls", "mcs"):
                continue
            default_idx = i - num_no_default
            if default_idx >= 0:
                args.append(self._ast_to_dummy(func.args.defaults[default_idx]))
            else:
                args.append(self._generate_default_arg(arg))
        arg_str = ", ".join(args)
        prefix = "await " if is_async else ""
        call = f"{prefix}{func.name}({arg_str})"
        header = "@pytest.mark.asyncio\n" if is_async else ""
        if self._has_return(func):
            body = f"result = {call}\nassert result is not None"
        else:
            body = f"{call}\nassert True"
        indent = "        "
        return (
            f"{header}"
            f"    def test_{func.name}(self):\n"
            f'        """Test {func.name}."""\n'
            f"{indent}{body.replace(chr(10), chr(10) + indent)}"
        )

    def _has_return(self, node: ast.AST) -> bool:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Return) and child.value is not None:
                return True
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if self._has_return(child):
                return True
        return False

    def _ast_to_dummy(self, node: ast.AST) -> str:
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
        if isinstance(node, ast.Name) and node.id in ("None", "True", "False"):
            return node.id
        return "None"

    def phase4_formatting(self) -> Dict[str, Any]:
        if not self.quiet:
            print("  Phase 4: Formatting...")
        result: Dict[str, Any] = {"status": "success", "tools_used": []}

        for tool in ("black", "isort"):
            if not self.dry_run and shutil.which(tool):
                try:
                    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False, encoding="utf-8") as tmp:
                        tmp.write(self.code)
                        tmp_path = Path(tmp.name)
                    proc = subprocess.run([tool, str(tmp_path), "--quiet"],
                                          capture_output=True, text=True, timeout=15)
                    if proc.returncode == 0:
                        self.code = tmp_path.read_text(encoding="utf-8")
                        result["tools_used"].append(tool)
                    tmp_path.unlink(missing_ok=True)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

        if not result["tools_used"]:
            lines = [line.rstrip() for line in self.code.split("\n")]
            cleaned, prev_blank = [], False
            for line in lines:
                if not line.strip():
                    if not prev_blank:
                        cleaned.append(line)
                    prev_blank = True
                else:
                    cleaned.append(line)
                    prev_blank = False
            if not self.dry_run:
                self.code = "\n".join(cleaned)
            result["tools_used"].append("basic-formatter")

        return result

    def phase5_validation(self) -> Dict[str, Any]:
        if not self.quiet:
            print("  Phase 5: Final Validation...")
        try:
            compile(self.code, str(self.filepath), "exec")
            return {"status": "success", "syntax_valid": True, "error": None,
                    "final_lines": len(self.code.split("\n"))}
        except SyntaxError as exc:
            return {"status": "failed", "syntax_valid": False, "error": f"Linha {exc.lineno}: {exc.msg}",
                    "final_lines": len(self.code.split("\n"))}

    def generate_diff(self) -> str:
        if self.original_code == self.code:
            return "Sem alteracoes."
        orig = self.original_code.split("\n")
        new = self.code.split("\n")
        diff_lines = []
        for i in range(max(len(orig), len(new))):
            o = orig[i] if i < len(orig) else ""
            n = new[i] if i < len(new) else ""
            if o != n:
                diff_lines.extend([f"- Linha {i+1}: {o}", f"+ Linha {i+1}: {n}"])
                if len(diff_lines) >= 20:
                    diff_lines.append("... (mais alteracoes omitidas)")
                    break
        return "\n".join(diff_lines) if diff_lines else "Sem alteracoes detectadas."

    def generate_patch(self) -> str:
        """Return a git apply-able unified diff with L3 contextual comments."""
        import difflib
        original_lines = self.original_code.splitlines(keepends=True)
        modified_lines = self.code.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines, modified_lines,
            fromfile=f"a/{self.filepath.name}",
            tofile=f"b/{self.filepath.name}",
            lineterm="",
        )
        patch_lines = list(diff)
        if not patch_lines:
            return ""
        comments = []
        for ch in self.changes:
            comments.append(f"# [{ch['type']}] {ch['description']}")
        if comments:
            return "\n".join(comments) + "\n" + "\n".join(patch_lines)
        return "\n".join(patch_lines)

    def save_patch(self) -> str:
        """Write the unified diff patch to reports/<file>_suggestions.patch and return its path."""
        patch_content = self.generate_patch()
        patch_path = self.artifacts.path_for("report", f"{self.filepath.stem}_suggestions.patch")
        if patch_content:
            patch_path.write_text(patch_content, encoding="utf-8")
        else:
            patch_path.write_text("# Nenhuma alteracao sugerida.\n", encoding="utf-8")
        self.artifacts.record("report", patch_path, description="Patch de sugestoes git apply")
        return str(patch_path)

    def execute_refactoring(self) -> Dict[str, Any]:
        mode = "DRY-RUN" if self.dry_run else "APLICANDO"
        if self.quiet:
            print(f"\nIMPLEMENTATION [{mode}]")
        else:
            print(f"\n{'='*60}\nIMPLEMENTATION (5 MICRO-PHASES) [{mode}]\n{'='*60}\n")

        results: Dict[str, Any] = {"phases": {}, "dry_run": self.dry_run}
        results["phases"]["1_setup"] = self.phase1_setup()
        results["phases"]["2_refactor"] = self.phase2_refactor_structure()
        results["patch_file"] = self.save_patch()
        results["phases"]["3_tests"] = self.phase3_tests()
        results["phases"]["4_formatting"] = self.phase4_formatting()
        results["phases"]["5_validation"] = self.phase5_validation()
        results["diff"] = self.generate_diff()
        results["total_changes"] = len(self.changes)

        if not results["phases"]["5_validation"]["syntax_valid"]:
            results["error"] = "Refatoracao abortada porque a validacao final detectou erro de sintaxe"
            manifest_path = self.artifacts.save_manifest({
                "mode": mode, "changes_found": len(self.changes),
                "validation": results["phases"]["5_validation"], "error": results["error"],
            })
            results["manifest"] = str(manifest_path)
            if not self.quiet:
                print("\nREFACTORING ABORTED - validacao final falhou.\n")
            return results

        if not self.dry_run:
            self.filepath.write_text(self.code, encoding="utf-8")
            results["refactored_file"] = str(self.filepath)
            results["backup_file"] = str(self.backup_path)
            diff_path = self.artifacts.path_for("refactor", f"{self.filepath.stem}_diff.txt")
            diff_path.write_text(self.generate_diff(), encoding="utf-8")
            self.artifacts.record("refactor", diff_path, description="Diff resumido da refatoração aplicada")
            if not self.quiet:
                print("\nREFACTORING COMPLETED!\n")
        else:
            if not self.quiet:
                print("\nDRY-RUN COMPLETE - nenhum arquivo foi modificado.\n")
                print("Use sem --dry-run para aplicar as alteracoes.\n")

        manifest_path = self.artifacts.save_manifest({
            "mode": mode, "changes_found": len(self.changes),
            "validation": results["phases"]["5_validation"],
        })
        results["manifest"] = str(manifest_path)
        return results


def refactor_file(
    filepath: str,
    dry_run: bool = False,
    output_dir: Optional[str] = None,
    structured_outputs: bool = True,
    artifact_registry: Optional[ArtifactRegistry] = None,
    quiet: bool = False,
    generate_tests: bool = True,
    enabled_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    try:
        orch = RefactoringOrchestrator(
            filepath,
            dry_run=dry_run,
            output_dir=output_dir,
            structured_outputs=structured_outputs,
            artifact_registry=artifact_registry,
            quiet=quiet,
            generate_tests=generate_tests,
            enabled_rules=enabled_rules,
        )
        return orch.execute_refactoring()
    except Exception as exc:
        return {"error": f"Erro: {exc}"}


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
