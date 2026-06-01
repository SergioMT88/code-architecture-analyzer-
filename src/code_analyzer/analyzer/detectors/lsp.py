"""LSP detector — Liskov Substitution Principle violations in subclasses."""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _self_attrs_assigned(method_node: ast.FunctionDef) -> Set[str]:
    """Return names of self.X attributes assigned (stored) in a method."""
    attrs: Set[str] = set()
    for node in ast.walk(method_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and isinstance(node.ctx, ast.Store)
        ):
            attrs.add(node.attr)
    return attrs


def _is_abstract_class(class_node: ast.ClassDef) -> bool:
    """True if the class is an abstract base: inherits ABC/ABCMeta, or has any
    method decorated @abstractmethod. Such classes legitimately raise
    NotImplementedError as an abstract declaration — not an LSP violation."""
    for base in class_node.bases:
        base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        if base_name in ("ABC", "ABCMeta"):
            return True
    for kw in class_node.keywords:
        if kw.arg == "metaclass" and getattr(kw.value, "id", "") == "ABCMeta":
            return True
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in item.decorator_list:
                dec_name = dec.id if isinstance(dec, ast.Name) else getattr(dec, "attr", "")
                if dec_name == "abstractmethod":
                    return True
    return False


def _is_abstractmethod(method_node: ast.AST) -> bool:
    for dec in getattr(method_node, "decorator_list", []):
        dec_name = dec.id if isinstance(dec, ast.Name) else getattr(dec, "attr", "")
        if dec_name == "abstractmethod":
            return True
    return False


def _raises_not_implemented(method_node: ast.AST) -> bool:
    """True if the method's body is essentially a refusal: raise NotImplementedError."""
    for stmt in getattr(method_node, "body", []):
        if isinstance(stmt, ast.Raise) and stmt.exc is not None:
            exc = stmt.exc
            name = ""
            if isinstance(exc, ast.Call):
                name = getattr(exc.func, "id", "") or getattr(exc.func, "attr", "")
            elif isinstance(exc, ast.Name):
                name = exc.id
            if name == "NotImplementedError":
                return True
    return False


def _leading_raise_guard(method_node: ast.AST) -> "ast.AST | None":
    """If the method starts with `if <cond>: raise <Exc>`, return that exception node.
    This is a strengthened precondition — a classic LSP violation in an override."""
    for stmt in getattr(method_node, "body", []):
        if isinstance(stmt, ast.If):
            for inner in stmt.body:
                if isinstance(inner, ast.Raise) and inner.exc is not None:
                    return inner.exc
        # Stop at the first real (non-docstring) statement.
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)):
            break
    return None


@register
class LSPDetector(Detector):
    name = "LSP"
    severity = "ALTA"
    penalty_per_finding = 3
    default_confidence = 0.75
    description = "Liskov Substitution Principle — subclass changes parent contract"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        if ctx.tree is None:
            return []

        findings: List[Finding] = []

        # Map every class to its methods so overrides can be resolved in-file.
        class_methods = {
            cn.name: {
                m.name: m for m in cn.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            for cn in ctx.get_nodes_by_type(ast.ClassDef)
        }

        for class_node in ctx.get_nodes_by_type(ast.ClassDef):
            if not class_node.bases:
                continue

            abstract_class = _is_abstract_class(class_node)
            base_names = [
                b.id if isinstance(b, ast.Name) else getattr(b, "attr", "")
                for b in class_node.bases
            ]

            for item in class_node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                # Resolve the inherited method (if the base is defined in this file).
                base_method = None
                for bn in base_names:
                    base_method = class_methods.get(bn, {}).get(item.name)
                    if base_method is not None:
                        break

                # Check 2: concrete subclass refuses an inherited method with
                # NotImplementedError, where the base declares it as abstract-ish
                # (also raises NotImplementedError or is @abstractmethod). The
                # interface forces a method this impl can't honor — contract/ISP/LSP
                # violation. Requiring an abstract-ish base keeps a plain default
                # method (e.g. `def speak(self): pass`) from being flagged.
                if (
                    base_method is not None
                    and not abstract_class
                    and not _is_abstractmethod(item)
                    and _raises_not_implemented(item)
                    and (_raises_not_implemented(base_method) or _is_abstractmethod(base_method))
                ):
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"classe '{class_node.name}', metodo '{item.name}', linha {item.lineno}",
                        line=item.lineno,
                        severity=self.severity,
                        issue=(
                            f"'{class_node.name}.{item.name}' levanta NotImplementedError numa classe "
                            "concreta — recusa implementar um metodo que a interface exige. Substituir o "
                            "pai por esta subclasse quebra em runtime (violacao LSP/ISP)."
                        ),
                        suggestion=(
                            "Implemente o metodo, ou separe a interface para que esta classe nao seja "
                            "obrigada a oferecer um metodo que nao suporta (Interface Segregation)."
                        ),
                        line_content=ctx.get_line(item.lineno),
                    ))

                # Check 3: override strengthens the precondition with a raise-guard
                # the base method does not have (e.g. Square.scale on Rectangle.scale).
                if base_method is not None:
                    guard = _leading_raise_guard(item)
                    if guard is not None and _leading_raise_guard(base_method) is None:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"classe '{class_node.name}', metodo '{item.name}', linha {item.lineno}",
                            line=item.lineno,
                            severity=self.severity,
                            issue=(
                                f"'{class_node.name}.{item.name}' fortalece a pre-condicao do metodo "
                                f"herdado (levanta excecao que o pai nunca levanta). Substituir o pai por "
                                "esta subclasse pode quebrar chamadores (violacao LSP)."
                            ),
                            suggestion=(
                                "Nao fortaleca pre-condicoes em overrides. Se o comportamento e diferente, "
                                "reavalie a heranca (ex.: Square nao deve herdar Rectangle — prefira composicao)."
                            ),
                            line_content=ctx.get_line(item.lineno),
                        ))

                # Check 1: set_X assigns self.Y where Y ≠ X — unexpected side effect
                name = item.name
                if name.startswith("set_") and len(name) > 4:
                    expected_attr = name[4:]
                    assigned = _self_attrs_assigned(item)
                    unexpected = assigned - {expected_attr}
                    if unexpected:
                        extra = ", ".join(f"self.{a}" for a in sorted(unexpected))
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"classe '{class_node.name}', metodo '{name}', linha {item.lineno}",
                            line=item.lineno,
                            severity=self.severity,
                            issue=(
                                f"'{class_node.name}.{name}' modifica atributos extras ({extra}) "
                                f"alem de 'self.{expected_attr}'. Subclasse quebra o contrato do pai "
                                "(violacao LSP): substituir o pai por esta subclasse muda o comportamento."
                            ),
                            suggestion=(
                                f"Remova os efeitos colaterais em {extra}. Se o comportamento e "
                                "fundamentalmente diferente, reavalie a hierarquia — talvez Square nao "
                                "deva herdar Rectangle (composicao sobre heranca)."
                            ),
                            line_content=ctx.get_line(item.lineno),
                        ))


        return findings[:MAX_FINDINGS_PER_DETECTOR]
