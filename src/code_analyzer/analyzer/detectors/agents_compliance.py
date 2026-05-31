"""AgentsCompliance detector — validates project rules defined in AGENTS.md ## [rules]."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, List, Set

from code_analyzer.analyzer.detectors import Detector, Finding, register

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


def _decorator_names(func: ast.FunctionDef) -> Set[str]:
    names: Set[str] = set()
    for d in func.decorator_list:
        if isinstance(d, ast.Name):
            names.add(d.id)
            names.add(f"@{d.id}")
        elif isinstance(d, ast.Attribute):
            names.add(d.attr)
            names.add(f"@{d.attr}")
        elif isinstance(d, ast.Call):
            f = d.func
            if isinstance(f, ast.Name):
                names.add(f.id)
                names.add(f"@{f.id}")
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
                names.add(f"@{f.attr}")
    return names


def _param_names(func: ast.FunctionDef) -> Set[str]:
    args = func.args
    names: Set[str] = {a.arg for a in args.args + args.posonlyargs + args.kwonlyargs}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


@register
class AgentsComplianceDetector(Detector):
    name = "AgentsCompliance"
    severity = "ALTA"
    description = "Project rules defined in AGENTS.md ## [rules] section"
    penalty_per_finding = 3
    default_confidence = 0.7

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []

        from code_analyzer.agents_rules import find_agents_md, parse_rules, rules_for_file

        agents_md = find_agents_md(Path(ctx.filepath))
        if agents_md is None:
            return []

        all_rules = parse_rules(agents_md)
        if not all_rules:
            return []

        filepath = Path(ctx.filepath)
        applicable = rules_for_file(filepath, all_rules)
        if not applicable:
            return []

        findings: List[Finding] = []
        functions = ctx.get_nodes_by_type(ast.FunctionDef, ast.AsyncFunctionDef)

        for rule in applicable:
            if rule.rule_type == "forbidden":
                pattern = rule.constraint_value
                # Normalize spaces around = so "fields='__all__'" matches "fields = '__all__'"
                pattern_norm = pattern.replace(" ", "")
                code_norm = ctx.code.replace(" ", "")
                if pattern_norm in code_norm:
                    lineno = next(
                        (i + 1 for i, ln in enumerate(ctx.lines)
                         if pattern_norm in ln.replace(" ", "")), 1
                    )
                    findings.append(Finding(
                        criterion=self.name,
                        location=f"linha {lineno}",
                        line=lineno,
                        severity="ALTA",
                        issue=f"Padrao proibido pelo AGENTS.md: {pattern!r}",
                        suggestion=f"Remova ou substitua o padrao '{pattern}' conforme as regras do projeto.",
                        line_content=ctx.get_line(lineno),
                    ))

            elif rule.rule_type == "decorator":
                required = rule.constraint_value.lstrip("@")
                for func in functions:
                    names = _decorator_names(func)
                    if required not in names and f"@{required}" not in names:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {func.lineno}",
                            line=func.lineno,
                            severity="ALTA",
                            issue=(
                                f"Funcao '{func.name}' nao tem o decorador "
                                f"@{required} exigido pelo AGENTS.md."
                            ),
                            suggestion=f"Adicione @{required} antes de '{func.name}'.",
                            line_content=ctx.get_line(func.lineno),
                        ))

            elif rule.rule_type == "param":
                required = rule.constraint_value
                for func in functions:
                    params = _param_names(func)
                    if required not in params:
                        findings.append(Finding(
                            criterion=self.name,
                            location=f"linha {func.lineno}",
                            line=func.lineno,
                            severity="ALTA",
                            issue=(
                                f"Funcao '{func.name}' nao tem o parametro "
                                f"'{required}' exigido pelo AGENTS.md."
                            ),
                            suggestion=f"Adicione o parametro '{required}' a '{func.name}'.",
                            line_content=ctx.get_line(func.lineno),
                        ))

        return findings
