"""String concatenation inside loop detector (O(n^2) pattern)."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class StringConcatInLoopDetector(Detector):
    name = "StringConcatInLoop"
    severity = "ALTA"
    penalty_per_finding = 3
    description = "StringConcatInLoop - s += x inside loop is O(n^2); prefer list + ''.join()"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return findings

        # Construir mapeamento de pai-filho
        parent_map = {}
        for parent in ast.walk(tree):
            for child_node in ast.iter_child_nodes(parent):
                parent_map[child_node] = parent

        def _is_initialized_as_non_string(loop_node: ast.For, var_name: str) -> bool:
            curr = loop_node
            parent_scope = None
            while curr in parent_map:
                curr = parent_map[curr]
                if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                    parent_scope = curr
                    break
            
            if not parent_scope:
                parent_scope = tree

            last_assigned_val = None
            for scope_node in ast.walk(parent_scope):
                if isinstance(scope_node, ast.Assign):
                    for target in scope_node.targets:
                        if isinstance(target, ast.Name) and target.id == var_name:
                            if scope_node.lineno < loop_node.lineno:
                                last_assigned_val = scope_node.value
                elif isinstance(scope_node, ast.AnnAssign):
                    if isinstance(scope_node.target, ast.Name) and scope_node.target.id == var_name:
                        if scope_node.lineno < loop_node.lineno and scope_node.value is not None:
                            last_assigned_val = scope_node.value

            if last_assigned_val is not None:
                if isinstance(last_assigned_val, ast.Constant):
                    if isinstance(last_assigned_val.value, (int, float, complex, bool)):
                        return True
                elif isinstance(last_assigned_val, ast.Num):
                    return True
                elif isinstance(last_assigned_val, ast.NameConstant) and isinstance(last_assigned_val.value, bool):
                    return True
                elif isinstance(last_assigned_val, (ast.List, ast.Dict, ast.Set)):
                    if not (hasattr(last_assigned_val, "elts") and last_assigned_val.elts) and not (hasattr(last_assigned_val, "keys") and last_assigned_val.keys):
                        return True
            return False

        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            loop_var = node.target.id if isinstance(node.target, ast.Name) else None

            for child in ast.walk(node):
                if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                    if isinstance(child.target, ast.Name) and child.target.id != loop_var:
                        # Ignorar se o operando adicionado for sabidamente numérico/booleano
                        added_val = child.value
                        if isinstance(added_val, ast.Constant) and isinstance(added_val.value, (int, float, complex, bool)):
                            continue
                        if isinstance(added_val, ast.Num):
                            continue
                        if isinstance(added_val, ast.NameConstant) and isinstance(added_val.value, bool):
                            continue
                        
                        # Verificar inicialização no escopo
                        if _is_initialized_as_non_string(node, child.target.id):
                            continue

                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {child.lineno}",
                            line=child.lineno,
                            severity="ALTA",
                            issue=f"'{child.target.id} += ...' dentro de loop pode ser lento com strings (O(n^2)).",
                            suggestion="Acumule partes em uma lista e use '\"\".join(partes)' no final.",
                            line_content=ctx.get_line(child.lineno),
                        ))
                elif (
                    isinstance(child, ast.Assign)
                    and len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Name)
                    and isinstance(child.value, ast.BinOp)
                    and isinstance(child.value.op, ast.Add)
                    and isinstance(child.value.left, ast.Name)
                    and child.value.left.id == child.targets[0].id
                    and child.targets[0].id != loop_var
                ):
                    # Ignorar se o operando adicionado for sabidamente numérico/booleano
                    added_val = child.value.right
                    if isinstance(added_val, ast.Constant) and isinstance(added_val.value, (int, float, complex, bool)):
                        continue
                    if isinstance(added_val, ast.Num):
                        continue
                    if isinstance(added_val, ast.NameConstant) and isinstance(added_val.value, bool):
                        continue

                    # Verificar inicialização no escopo
                    if _is_initialized_as_non_string(node, child.targets[0].id):
                        continue

                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {child.lineno}",
                        line=child.lineno,
                        severity="ALTA",
                        issue=f"'{child.targets[0].id} = {child.targets[0].id} + ...' dentro de loop pode ser lento (O(n^2)).",
                        suggestion="Acumule partes em uma lista e use '\"\".join(partes)' no final.",
                        line_content=ctx.get_line(child.lineno),
                    ))

        return findings
