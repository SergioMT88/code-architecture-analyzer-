"""DataFlowExtractor detector — suggests extraction boundaries in long functions."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from code_analyzer.analyzer.detectors import Detector, Finding, register
from code_analyzer.analyzer.dataflow import analyze_file

if TYPE_CHECKING:
    from code_analyzer.analyzer.context import AnalysisContext


@register
class DataFlowExtractorDetector(Detector):
    name = "DataFlowExtractor"
    severity = "BAIXA"
    description = (
        "Data-flow cluster analysis — identifies extractable sub-functions "
        "within long methods via def-use dependency grouping"
    )
    penalty_per_finding = 1

    def detect(self, ctx: "AnalysisContext") -> List[Finding]:
        if ctx.is_ignored(self.name):
            return []
        if ctx.tree is None:
            return []

        findings: List[Finding] = []
        results = analyze_file(ctx.tree)

        for func_result in results:
            func_name = func_result["function"]
            func_line = func_result["function_line"]
            func_end = func_result["function_end"]
            func_span = func_end - func_line

            for candidate in func_result["candidates"][:2]:
                vars_str = ", ".join(f"'{v}'" for v in candidate["variables"][:4])
                extra = f" (+{len(candidate['variables']) - 4} vars)" if len(candidate["variables"]) > 4 else ""
                findings.append(Finding(
                    criterion=self.name,
                    location=f"linhas {candidate['start_line']}-{candidate['end_line']}",
                    line=candidate["start_line"],
                    severity=self.severity,
                    issue=(
                        f"Funcao '{func_name}' ({func_span} linhas): cluster coeso em "
                        f"linhas {candidate['start_line']}-{candidate['end_line']} "
                        f"({candidate['span']} linhas). "
                        f"Variaveis locais: {vars_str}{extra}."
                    ),
                    suggestion=(
                        f"Extraia para '{candidate['suggested_name']}()'. "
                        "O cluster opera sobre variaveis que nao cruzam com o resto da funcao."
                    ),
                    line_content=ctx.get_line(candidate["start_line"]),
                ))

        return findings
