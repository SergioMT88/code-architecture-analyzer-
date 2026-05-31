"""MassAssignment detector — fields = '__all__' in ModelForm/ModelSerializer subclasses."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.detectors._utils import class_bases

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_DANGEROUS_BASES = frozenset({
    "ModelForm",
    "ModelSerializer",
    "HyperlinkedModelSerializer",
    "ModelViewSet",
    "ReadOnlyModelViewSet",
})

_PERMISSION_FIELD_HINTS = frozenset({"is_admin", "is_staff", "is_superuser", "is_active", "role", "permission"})


def _has_all_fields_assign(class_body: List[ast.stmt]) -> int:
    """Return lineno of `fields = '__all__'` if found, else 0."""
    for stmt in class_body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "fields":
                    if isinstance(stmt.value, ast.Constant) and stmt.value.value == "__all__":
                        return stmt.lineno
    return 0


def _has_empty_exclude(class_body: List[ast.stmt]) -> int:
    """Return lineno of `exclude = []` (empty list) if found, else 0."""
    for stmt in class_body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "exclude":
                    if isinstance(stmt.value, (ast.List, ast.Tuple)) and not stmt.value.elts:
                        return stmt.lineno
    return 0


@register
class MassAssignmentDetector(Detector):
    name = "MassAssignment"
    severity = "ALTA"
    penalty_per_finding = 4
    default_confidence = 0.75
    description = "Mass assignment — fields = '__all__' exposes all model fields including sensitive ones"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        seen_lines: Set[int] = set()

        # Django-style: fields = '__all__' in ModelForm/ModelSerializer
        for node in ctx.get_nodes_by_type(ast.ClassDef):
            bases = class_bases(node)
            is_dangerous = any(b in _DANGEROUS_BASES for b in bases)

            # Check fields = '__all__' directly in class body (dangerous bases only)
            if is_dangerous:
                lineno = _has_all_fields_assign(node.body)
                if lineno and lineno not in seen_lines:
                    seen_lines.add(lineno)
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe {node.name}, linha {lineno}",
                        line=lineno,
                        severity="ALTA",
                        issue=(
                            f"Classe '{node.name}' usa fields = '__all__', expondo todos os campos do model "
                            "incluindo campos sensiveis como senhas, tokens, flags de permissao e timestamps internos."
                        ),
                        suggestion=(
                            "Substitua '__all__' por uma lista explicita dos campos necessarios: "
                            "fields = ['campo1', 'campo2']. Nunca exponha campos como password, token, "
                            "is_admin, is_staff ou outros campos de controle via '__all__'."
                        ),
                        line_content=ctx.get_line(lineno),
                    ))
                excl_lineno = _has_empty_exclude(node.body)
                if excl_lineno and excl_lineno not in seen_lines:
                    seen_lines.add(excl_lineno)
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe {node.name}, linha {excl_lineno}",
                        line=excl_lineno,
                        severity="ALTA",
                        issue=(
                            f"Classe '{node.name}' usa exclude = [] (lista vazia), expondo todos os campos "
                            "do model — equivalente a fields = '__all__'."
                        ),
                        suggestion=(
                            "Use fields = ['campo1', 'campo2'] em vez de exclude vazio. "
                            "exclude = [] nao exclui nada e expoe todos os campos, incluindo sensiveis."
                        ),
                        line_content=ctx.get_line(excl_lineno),
                    ))

            # Check class Meta: fields = '__all__' or exclude = [] — ANY class (not just dangerous bases)
            for item in node.body:
                if not (isinstance(item, ast.ClassDef) and item.name == "Meta"):
                    continue
                meta_lineno = _has_all_fields_assign(item.body)
                if meta_lineno and meta_lineno not in seen_lines:
                    seen_lines.add(meta_lineno)
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe {node.name}.Meta, linha {meta_lineno}",
                        line=meta_lineno,
                        severity="ALTA",
                        issue=(
                            f"Classe '{node.name}' usa fields = '__all__' na Meta, expondo todos os campos "
                            "incluindo campos sensiveis (password, token, flags de permissao)."
                        ),
                        suggestion=(
                            "Substitua '__all__' por uma lista explicita: fields = ['campo1', 'campo2']. "
                            "Revise especialmente campos como is_staff, is_superuser, password e tokens."
                        ),
                        line_content=ctx.get_line(meta_lineno),
                    ))
                meta_excl_lineno = _has_empty_exclude(item.body)
                if meta_excl_lineno and meta_excl_lineno not in seen_lines:
                    seen_lines.add(meta_excl_lineno)
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe {node.name}.Meta, linha {meta_excl_lineno}",
                        line=meta_excl_lineno,
                        severity="ALTA",
                        issue=(
                            f"Classe '{node.name}' usa exclude = [] (lista vazia) na Meta, expondo todos os campos "
                            "— equivalente a fields = '__all__'."
                        ),
                        suggestion=(
                            "Use fields = ['campo1', 'campo2'] em vez de exclude vazio. "
                            "exclude = [] nao exclui nada e expoe todos os campos, incluindo sensiveis."
                        ),
                        line_content=ctx.get_line(meta_excl_lineno),
                    ))

        # Generic Python-style: **dict unpacking in function calls
        # e.g. criar_pedido(**request_data) — uncontrolled dict unpacking
        for node in ctx.get_nodes_by_type(ast.Call):
            for kw in node.keywords or []:
                if kw.arg is None and isinstance(kw.value, ast.Name):
                    lineno = node.lineno
                    if lineno not in seen_lines:
                        seen_lines.add(lineno)
                        func_name = _call_name(node)
                        if func_name is None:
                            func_name = "funcao"
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {lineno}",
                            line=lineno,
                            severity="ALTA",
                            issue=(
                                f"'{func_name}()' recebe **{kw.value.id} — "
                                "dict unpacking sem validacao explicita. "
                                "Se o dict vier de request/input do usuario, "
                                "qualquer chave inesperada pode contaminar o modelo."
                            ),
                            suggestion=(
                                f"Defina explicitamente os campos permitidos para {func_name}() "
                                f"em vez de passar **{kw.value.id} diretamente. "
                                "Use um schema validator (pydantic, dataclass) para controlar "
                                "quais campos sao aceitos."
                            ),
                            line_content=ctx.get_line(lineno),
                        ))

        return findings


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return f"{_attr_base(node.func.value)}.{node.func.attr}" if isinstance(node.func.value, ast.Name) else node.func.attr
    return None


def _attr_base(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_attr_base(node.value)}.{node.attr}"
    return "?"
