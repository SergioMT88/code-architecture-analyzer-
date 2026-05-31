"""ShotgunSurgery detector — a constant referenced in 3+ distinct classes."""
from __future__ import annotations

import ast
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.limits import MAX_FINDINGS_PER_DETECTOR

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext

_MIN_CLASSES = 3


def _collect_class_constant_usages(
    ctx: "AnalysisContext",
) -> Dict[Tuple[str, str], List[Tuple[str, int]]]:
    """
    Walk each top-level ClassDef and record every ClassName.ATTR access found inside.
    Returns {(src_class, attr): [(using_class, lineno), ...]}
    Only tracks accesses where src_class != using_class.
    """
    usages: Dict[Tuple[str, str], List[Tuple[str, int]]] = defaultdict(list)

    for class_node in ctx.get_nodes_by_type(ast.ClassDef):
        using_class = class_node.name
        for node in ast.walk(class_node):
            if not isinstance(node, ast.Attribute):
                continue
            if not isinstance(node.value, ast.Name):
                continue
            src = node.value.id
            if src == "self" or src == using_class:
                continue
            if not src[0].isupper():
                continue
            usages[(src, node.attr)].append((using_class, node.lineno))

    return usages


@register
class ShotgunSurgeryDetector(Detector):
    name = "ShotgunSurgery"
    severity = "MEDIA"
    penalty_per_finding = 2
    default_confidence = 0.7
    description = "Shotgun Surgery — changing one value requires touching many classes"

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        if ctx.tree is None:
            return []

        usages = _collect_class_constant_usages(ctx)
        findings: List[Finding] = []

        for (src_class, attr), accesses in usages.items():
            distinct_classes: Set[str] = {cls for cls, _ in accesses}
            if len(distinct_classes) < _MIN_CLASSES:
                continue
            first_lineno = accesses[0][1]
            classes_str = ", ".join(sorted(distinct_classes))
            findings.append(Finding(
                criterion=self.name,
                location=f"'{src_class}.{attr}' em {len(distinct_classes)} classes",
                line=first_lineno,
                severity=self.severity,
                issue=(
                    f"'{src_class}.{attr}' e referenciado em {len(distinct_classes)} classes diferentes "
                    f"({classes_str}). Uma mudanca neste valor obriga a revisar todas essas classes."
                ),
                suggestion=(
                    f"Centralize '{attr}' em um modulo de configuracao ou injete-o via dependencia. "
                    "Evite referencias espalhadas a constantes de outras classes."
                ),
                line_content=ctx.get_line(first_lineno),
            ))

        return findings[:MAX_FINDINGS_PER_DETECTOR]
