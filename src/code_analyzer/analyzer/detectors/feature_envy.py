"""FeatureEnvy detector — methods that access another object's data more than their own."""
from __future__ import annotations

import ast
from collections import Counter
from typing import TYPE_CHECKING, List, Set, Tuple

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.constants import (
    FEATURE_ENVY_FOREIGN_MULTIPLIER,
    FEATURE_ENVY_MIN_FOREIGN_ACCESSES,
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
)
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_MIN_FOREIGN_ACCESSES = 2
_MIN_RATIO = 1  # foreign must exceed own accesses

# Stdlib collection methods — calling these on self.X is normal data management, not Feature Envy
_COLLECTION_METHODS = frozenset({
    "append", "pop", "extend", "insert", "remove", "clear", "sort", "reverse", "copy",
    "update", "setdefault", "get", "keys", "values", "items",
    "add", "discard", "union", "intersection", "difference",
    "encode", "decode", "strip", "split", "join", "format",
})


def _analyze_method(method_node: ast.FunctionDef) -> Tuple[str, int, int] | None:
    """
    Returns (foreign_obj_name, foreign_count, own_count) if envy is detected, else None.
    Envy: method accesses self.X.Y chains more than plain self.X attributes.
    Collection method calls (append, pop, update, etc.) on self.X are excluded —
    those are normal data management, not feature envy.
    """
    foreign_obj_counts: Counter = Counter()
    is_foreign_base: Set[str] = set()

    for node in ast.walk(method_node):
        if not isinstance(node, ast.Attribute):
            continue
        # Detect self.X.Y — the outer node: value=Attribute(value=Name('self'), attr=X)
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "self"
        ):
            foreign_attr = node.value.attr
            # Skip collection/stdlib method calls on own attributes — not feature envy
            if node.attr in _COLLECTION_METHODS:
                continue
            foreign_obj_counts[foreign_attr] += 1
            is_foreign_base.add(foreign_attr)

    if not foreign_obj_counts:
        return None

    all_self_direct: Counter = Counter()
    for node in ast.walk(method_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            all_self_direct[node.attr] += 1

    # Own accesses = self.X where X is NOT used as a foreign object base
    own_count = sum(cnt for attr, cnt in all_self_direct.items() if attr not in is_foreign_base)
    total_foreign = sum(foreign_obj_counts.values())

    if total_foreign < _MIN_FOREIGN_ACCESSES:
        return None
    if total_foreign <= own_count:
        return None

    top_attr = foreign_obj_counts.most_common(1)[0][0]
    return top_attr, total_foreign, own_count


@register
class FeatureEnvyDetector(Detector):
    name = "FeatureEnvy"
    severity = "MEDIA"
    penalty_per_finding = 2
    description = "Feature Envy — method accesses another object's data more than its own"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        if ctx.tree is None:
            return []

        findings: List[Finding] = []

        for class_node in ctx.get_nodes_by_type(ast.ClassDef):
            for item in class_node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("_") and not item.name.startswith("__"):
                    continue

                result = _analyze_method(item)
                if result is None:
                    continue

                foreign_obj, foreign_count, own_count = result
                conf = HIGH_CONFIDENCE if (foreign_count >= own_count * FEATURE_ENVY_FOREIGN_MULTIPLIER or foreign_count >= FEATURE_ENVY_MIN_FOREIGN_ACCESSES) else MEDIUM_CONFIDENCE
                findings.append(Finding(
                    criterion=self.name,
                    location=f"classe '{class_node.name}', metodo '{item.name}', linha {item.lineno}",
                    line=item.lineno,
                    severity=self.severity,
                    issue=(
                        f"Metodo '{item.name}' acessa atributos de 'self.{foreign_obj}' "
                        f"{foreign_count}x vs {own_count}x proprios. "
                        "Indica que a logica pertence a outra classe (Feature Envy)."
                    ),
                    suggestion=(
                        f"Mova a logica de '{item.name}' para a classe de '{foreign_obj}', "
                        "ou crie um metodo la que encapsule esse comportamento."
                    ),
                    line_content=ctx.get_line(item.lineno),
                    confidence=conf,
                ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
