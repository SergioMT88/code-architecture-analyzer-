"""UselessListComp detector — no-op comprehensions like [x for x in xs].

Flags a list/set/dict comprehension that only copies the iterable without any
transformation or filtering: the element expression is exactly the loop target.
`[x for x in xs]` should be `list(xs)`; `{x for x in xs}` should be `set(xs)`.
"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, List, Optional

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _noop_target(comp: ast.AST) -> Optional[str]:
    """If *comp* is a no-op copy comprehension, return the builtin that replaces
    it ('list'/'set'/'dict'); otherwise None."""
    if isinstance(comp, (ast.ListComp, ast.SetComp)):
        elt = comp.elt
        generators = comp.generators
    else:
        return None

    # Exactly one generator, no filter conditions.
    if len(generators) != 1 or generators[0].ifs:
        return None
    gen = generators[0]
    if not isinstance(gen.target, ast.Name) or not isinstance(elt, ast.Name):
        return None
    if elt.id != gen.target.id:
        return None
    return "list" if isinstance(comp, ast.ListComp) else "set"


@register
class UselessListCompDetector(Detector):
    name = "UselessListComp"
    severity = "BAIXA"
    penalty_per_finding = 1
    default_confidence = 0.9
    description = (
        "UselessListComp - comprehension that only copies the iterable "
        "([x for x in xs]); use list()/set() directly"
    )

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        findings: List[Finding] = []
        for node in ctx.get_nodes_by_type(ast.ListComp, ast.SetComp):
            builtin = _noop_target(node)
            if builtin is None:
                continue
            findings.append(Finding(
                criterion=self.name,
                location=f"linha {node.lineno}",
                line=node.lineno,
                severity="BAIXA",
                issue=(
                    f"Comprehension sem transformacao nem filtro — apenas copia o iteravel. "
                    f"Use '{builtin}(...)' diretamente."
                ),
                suggestion=(
                    f"Substitua '[x for x in xs]' por '{builtin}(xs)': mais claro e rapido."
                ),
                line_content=ctx.get_line(node.lineno),
            ))
        return findings
