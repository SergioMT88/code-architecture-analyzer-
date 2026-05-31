"""InjectionRisk detector — SQL injection via raw()/extra()/cursor.execute() and command injection via os.system()."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_ORM_RAW_METHODS = frozenset({"raw", "extra"})
_DB_CURSOR_METHODS = frozenset({"execute", "executemany"})
_OS_EXEC_FUNCS = frozenset({"system", "popen"})
_SUBPROCESS_FUNCS = frozenset({"call", "run", "Popen", "check_call", "check_output"})


def _is_unsafe_arg(node: ast.AST) -> bool:
    """True if arg is an f-string, string concatenation, or %-format (not a plain literal)."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    return False


def _first_arg(call: ast.Call) -> "ast.AST | None":
    return call.args[0] if call.args else None


@register
class InjectionRiskDetector(Detector):
    name = "InjectionRisk"
    severity = "ALTA"
    penalty_per_finding = 5
    default_confidence = 0.9
    description = "Injection risk — SQL or command injection via unsafe string interpolation in raw queries or OS calls"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []

        for node in ctx.get_nodes_by_type(ast.Call):
            func = node.func

            # ORM: .raw(f"...") or .extra(where=[f"..."])
            if isinstance(func, ast.Attribute) and func.attr in _ORM_RAW_METHODS:
                arg = _first_arg(node)
                if arg and _is_unsafe_arg(arg):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=(
                            f"Injecao SQL potencial: .{func.attr}() com string interpolada. "
                            "Interpolar entrada do usuario em SQL raw permite ataques de injecao."
                        ),
                        suggestion=(
                            f"Use parametros posicionais: .{func.attr}('SELECT ... WHERE id = %s', [user_id]). "
                            "Nunca interpole variaveis diretamente no SQL."
                        ),
                        line_content=ctx.get_line(node.lineno),
                    ))

            # cursor.execute(f"...")
            elif isinstance(func, ast.Attribute) and func.attr in _DB_CURSOR_METHODS:
                arg = _first_arg(node)
                if arg and _is_unsafe_arg(arg):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=(
                            f"Injecao SQL potencial: cursor.{func.attr}() com string interpolada. "
                            "Interpolar entrada do usuario em SQL permite ataques de injecao."
                        ),
                        suggestion=(
                            f"Use parametros: cursor.{func.attr}('SELECT ... WHERE id = %s', [value]). "
                            "Nunca construa SQL com f-strings ou concatenacao de usuario."
                        ),
                        line_content=ctx.get_line(node.lineno),
                    ))

            # os.system(f"...") or os.popen(f"...")
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in _OS_EXEC_FUNCS
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                arg = _first_arg(node)
                if arg and _is_unsafe_arg(arg):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=(
                            f"Command injection potencial: os.{func.attr}() com string interpolada. "
                            "Entrada do usuario interpolada em comando de shell permite execucao arbitraria."
                        ),
                        suggestion=(
                            "Use subprocess.run(['cmd', arg1, arg2], ...) com lista de argumentos. "
                            "Nunca interpole entrada do usuario em comandos de shell."
                        ),
                        line_content=ctx.get_line(node.lineno),
                    ))

            # subprocess.call/run/Popen(f"...") — shell=True implied by f-string
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in _SUBPROCESS_FUNCS
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            ):
                arg = _first_arg(node)
                if arg and _is_unsafe_arg(arg):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {node.lineno}",
                        line=node.lineno,
                        severity="ALTA",
                        issue=(
                            f"Command injection potencial: subprocess.{func.attr}() com string interpolada. "
                            "String interpolada como argumento de subprocess permite command injection."
                        ),
                        suggestion=(
                            "Passe lista de argumentos: subprocess.run(['cmd', arg], shell=False). "
                            "Se shell=True for necessario, sanitize entrada com shlex.quote()."
                        ),
                        line_content=ctx.get_line(node.lineno),
                    ))

        return findings
