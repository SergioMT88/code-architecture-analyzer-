#!/usr/bin/env python3
"""
Report Generator v2.1.2 - Relatorios JSON e Markdown ricos com antes/depois.
"""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from artifact_manager import ArtifactRegistry


class ReportGenerator:
    """Gera relatorios estruturados com detalhamento por linha e sugestoes."""

    def __init__(
        self,
        filepath: str,
        analysis: Dict[str, Any],
        artifact_registry: Optional[ArtifactRegistry] = None,
        output_dir: Optional[str] = None,
        structured_outputs: bool = True,
    ):
        self.filepath = Path(filepath)
        self.analysis = analysis
        self.timestamp = datetime.now().isoformat()
        self.lines = self._load_source_lines()
        self.artifacts = artifact_registry or ArtifactRegistry(
            self.filepath,
            output_dir=output_dir,
            structured_outputs=structured_outputs,
        )

    def _load_source_lines(self) -> List[str]:
        try:
            return self.filepath.read_text(encoding='utf-8').split('\n')
        except Exception:
            return []

    def _write_text_atomic(self, path: Path, content: str) -> None:
        """Escreve texto de forma atomica para evitar arquivos vazios em falhas."""
        if not content or not content.strip():
            raise ValueError(f"Conteudo vazio para artefato: {path.name}")

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    def _get_snippet(self, lineno: int, context: int = 2) -> str:
        """Retorna trecho de codigo com contexto ao redor de uma linha."""
        if not self.lines or lineno <= 0:
            return ""
        start = max(0, lineno - context - 1)
        end = min(len(self.lines), lineno + context)
        snippet_lines = []
        for i, line in enumerate(self.lines[start:end], start=start + 1):
            marker = ">>>" if i == lineno else "   "
            snippet_lines.append(f"{marker} {i:4d} | {line}")
        return "\n".join(snippet_lines)

    def generate_json_report(self) -> Dict[str, Any]:
        recommendations = self._generate_recommendations()
        return {
            "metadata": {
                "timestamp": self.timestamp,
                "file_analyzed": str(self.filepath),
                "tool": "Code Architecture Analyzer v2.1.2",
                "version": "2.1.2",
                "output_root": str(self.artifacts.run_root),
                "analysis_dir": str(self.artifacts.analysis_dir),
                "reports_dir": str(self.artifacts.reports_dir),
            },
            "summary": self._generate_summary(),
            "metrics": self.analysis.get("metrics", {}),
            "criteria": self.analysis.get("criteria", {}),
            "dependencies": self.analysis.get("dependencies", {}),
            "test_analysis": self.analysis.get("test_analysis", {}),
            "tool_findings": self.analysis.get("tool_findings", {}),
            "config": self.analysis.get("config", {}),
            "action_summary": self._generate_action_summary(recommendations),
            "recommendations": recommendations,
        }

    def generate_markdown_report(self) -> str:
        """Gera relatorio Markdown rico. Fix: usa encoding UTF-8 na escrita."""
        parts = []

        parts.append(f"# Relatorio de Analise de Arquitetura - {self.filepath.name}")
        parts.append(f"\n**Data:** {self.timestamp}")
        parts.append(f"**Arquivo:** `{self.filepath}`")
        parts.append("**Ferramenta:** Code Architecture Analyzer v2.1.2\n")

        parts.append(self._section_summary())
        parts.append(self._section_action_plan())
        parts.append(self._section_metrics())
        parts.append(self._section_criteria())
        parts.append(self._section_dependencies())
        parts.append(self._section_tools())
        parts.append(self._section_tests())
        parts.append(self._section_recommendations())

        return "\n".join(parts)

    def _generate_summary(self) -> Dict[str, Any]:
        criteria = self.analysis.get("criteria", {})
        scores = [v.get("score", 0) for v in criteria.values()]
        avg = round(sum(scores) / max(1, len(scores)), 1)
        critical = [k for k, v in criteria.items() if v.get("score", 10) < 5]
        warnings = [k for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]
        metrics = self.analysis.get("metrics", {})
        return {
            "overall_score": avg,
            "grade": self._score_to_grade(avg),
            "critical_criteria": critical,
            "warning_criteria": warnings,
            "total_findings": sum(
                len(v.get("findings", [])) for v in criteria.values()
            ),
            "maintainability_grade": metrics.get("maintainability_grade", "N/A"),
        }

    def _score_to_grade(self, score: float) -> str:
        if score >= 9:
            return "A"
        elif score >= 7:
            return "B"
        elif score >= 5:
            return "C"
        else:
            return "D"

    def _section_summary(self) -> str:
        summary = self._generate_summary()
        lines = ["## Resumo Geral\n"]
        lines.append("| Item | Valor |")
        lines.append("|------|-------|")
        lines.append(f"| Score Geral | {summary['overall_score']}/10 (Grau {summary['grade']}) |")
        lines.append(
            f"| Manutenibilidade | {summary['maintainability_grade']} |"
        )
        lines.append(f"| Problemas Criticos | {len(summary['critical_criteria'])} |")
        lines.append(f"| Avisos | {len(summary['warning_criteria'])} |")
        lines.append(f"| Total de Findings | {summary['total_findings']} |")

        if summary['critical_criteria']:
            lines.append(
                f"\n**Criticos:** `{'`, `'.join(summary['critical_criteria'])}`"
            )
        if summary['warning_criteria']:
            lines.append(
                f"**Avisos:** `{'`, `'.join(summary['warning_criteria'])}`"
            )
        return "\n".join(lines)

    def _section_action_plan(self) -> str:
        recs = self._generate_recommendations()
        if not recs:
            return "\n## Proximas Acoes\n\nNenhuma acao prioritaria encontrada.\n"

        lines = ["\n## Proximas Acoes\n"]
        lines.append("| # | Prioridade | Foco | Impacto | Confianca | Proxima acao |")
        lines.append("|---|---|---|---|---|---|")

        for i, rec in enumerate(recs[:5], 1):
            lines.append(
                f"| {i} | {rec.get('priority', 'MEDIA')} | "
                f"{self._inline_text(rec.get('title', ''))} | "
                f"{self._inline_text(rec.get('impact', 'Impacto moderado'))} | "
                f"{self._inline_text(rec.get('confidence', 'Media'))} | "
                f"{self._inline_text(rec.get('next_step', rec.get('action', '')))} |"
            )

        top = recs[0]
        lines.append("")
        lines.append("**Decisao rapida:**")
        lines.append(
            f"Comece por `{top.get('title', '')}` porque "
            f"{top.get('why_now', top.get('description', ''))}."
        )
        if top.get("manual_review"):
            lines.append(
                "Essa acao pede revisao manual antes de aplicar automaticamente."
            )

        return "\n".join(lines)

    def _section_metrics(self) -> str:
        metrics = self.analysis.get("metrics", {})
        lines = ["\n## Metricas de Codigo\n"]
        lines.append("| Metrica | Valor |")
        lines.append("|---------|-------|")
        lines.append(f"| Linhas totais | {metrics.get('lines_of_code', 0)} |")
        lines.append(f"| Linhas de codigo | {metrics.get('code_lines', 0)} |")
        lines.append(f"| Linhas de comentario | {metrics.get('comment_lines', 0)} |")
        lines.append(f"| Ratio comentarios | {metrics.get('comment_ratio', 0)}% |")
        if "comment_ratio_target" in metrics:
            status = "Sim" if metrics.get("comment_ratio_ok") else "Nao"
            lines.append(
                f"| Alvo comentarios | {metrics.get('comment_ratio_target', 0)}% |"
            )
            lines.append(f"| Atingiu alvo | {status} |")
        lines.append(f"| Classes | {metrics.get('num_classes', 0)} |")
        lines.append(f"| Funcoes | {metrics.get('num_functions', 0)} |")
        lines.append(f"| Imports unicos | {metrics.get('num_imports', 0)} |")
        lines.append(
            f"| Complexidade media | {metrics.get('avg_cyclomatic_complexity', 0)} |"
        )
        lines.append(
            f"| Complexidade maxima | {metrics.get('max_cyclomatic_complexity', 0)} |"
        )
        lines.append(
            f"| Maintainability Index | "
            f"{metrics.get('maintainability_index', 0)} "
            f"({metrics.get('maintainability_grade', 'N/A')}) |"
        )
        return "\n".join(lines)

    def _section_criteria(self) -> str:
        criteria = self.analysis.get("criteria", {})
        lines = ["\n## Analise por Criterio\n"]

        for key, value in criteria.items():
            score = value.get("score", 0)
            status = value.get("status", "N/A")
            desc = value.get("description", "")
            findings = value.get("findings", [])
            severity = value.get("severity", "MEDIA")

            bar = self._score_bar(score)
            lines.append(f"### {key}")
            lines.append(
                f"**Score:** {score}/10 {bar} | **Status:** {status} | **Severidade:** {severity}")
            if desc:
                lines.append(f"*{desc}*")
            lines.append("")

            if findings:
                lines.append(f"**{len(findings)} problema(s) encontrado(s):**\n")
                for i, finding in enumerate(findings, 1):
                    loc = finding.get("location", "")
                    issue = finding.get("issue", "")
                    sug = finding.get("suggestion", "")
                    content = finding.get("line_content", "")
                    patterns = finding.get("patterns", [])
                    meta = self._finding_meta(finding, score)

                    lines.append(f"**{i}. [{loc}]** {issue}")
                    lines.append(f"- Impacto estimado: {meta['impact']}")
                    lines.append(f"- Confiança: {meta['confidence']}")
                    if patterns:
                        pattern_names = ", ".join(p.get("pattern", "") for p in patterns if p.get("pattern"))
                        if pattern_names:
                            lines.append(f"- Padrões detectados: {pattern_names}")
                    if content:
                        lines.append(f"\n```python\n# Codigo atual ({loc}):\n{content}\n```")
                    if sug:
                        lines.append(f"\n> **Sugestao:** {sug}\n")
                    else:
                        lines.append("")
            else:
                lines.append("Sem problemas detectados automaticamente.\n")

        return "\n".join(lines)

    def _section_dependencies(self) -> str:
        deps = self.analysis.get("dependencies", {})
        if not deps:
            return ""

        lines = ["\n## Analise de Dependencias\n"]
        lines.append(f"- **Total de imports:** {deps.get('total_imports', 0)}")
        lines.append(f"- **Modulos unicos:** {deps.get('unique_modules', 0)}")

        third = deps.get("third_party", [])
        if third:
            lines.append(f"- **Dependencias externas:** `{'`, `'.join(third)}`")

        duplicates = deps.get("duplicate_imports", [])
        if duplicates:
            lines.append("\n**Imports duplicados encontrados:**\n")
            for d in duplicates:
                lines.append(
                    f"- Linha {d['lineno']}: `{d['module']}` - {d['issue']}"
                )

        circular = deps.get("circular_dependencies", [])
        if circular:
            lines.append("\n**Dependencias circulares encontradas:**\n")
            for cycle in circular[:10]:
                path = cycle.get("path", [])
                if path:
                    lines.append(f"- `{' -> '.join(path)}`")
                    import_line = cycle.get("import_line")
                    if import_line:
                        lines.append(f"  > Linha de entrada no modulo atual: {import_line}")

        inline = deps.get("inline_imports", [])
        if inline:
            lines.append("\n**Imports dentro de funcoes (anti-pattern):**\n")
            for imp in inline:
                lines.append(
                    f"- Linha {imp['lineno']}: `import {imp['module']}` "
                    f"dentro de `{imp['inside_function']}()`"
                )
                lines.append(f"  > {imp.get('suggestion', '')}")

        coupling = deps.get("coupling_score", {})
        if coupling.get("issues"):
            lines.append("\n**Problemas de acoplamento:**\n")
            for issue in coupling["issues"]:
                lines.append(f"- {issue}")

        return "\n".join(lines)

    def _section_tools(self) -> str:
        tool_findings = self.analysis.get("tool_findings", {})
        if not tool_findings or tool_findings.get("total", 0) == 0:
            return "\n## Ferramentas Externas\n\nRuff e Pylint nao encontrados ou sem problemas.\n"

        lines = ["\n## Ferramentas Externas\n"]

        for tool in ["ruff", "pylint"]:
            findings = tool_findings.get(tool, [])
            if findings:
                lines.append(f"### {tool.capitalize()} ({len(findings)} ocorrencias)\n")
                for f in findings[:10]:
                    lines.append(
                        f"- **Linha {f.get('lineno', '?')}** "
                        f"[{f.get('code', '')}]: {f.get('issue', '')}"
                    )
                lines.append("")

        return "\n".join(lines)

    def _section_tests(self) -> str:
        tests = self.analysis.get("test_analysis", {})
        if not tests:
            return ""

        lines = ["\n## Analise de Testes\n"]
        lines.append("| Item | Valor |")
        lines.append("|------|-------|")
        lines.append(f"| Funcoes de teste | {tests.get('test_functions', 0)} |")
        lines.append(f"| Classes de teste | {tests.get('test_classes', 0)} |")
        lines.append(f"| Usa pytest | {'Sim' if tests.get('uses_pytest') else 'Nao'} |")
        lines.append(f"| Cobertura estimada | {tests.get('estimated_coverage', 0)}% |")

        missing = tests.get("missing_tests", [])
        if missing:
            lines.append(f"\n**Metodos sem testes ({len(missing)}):**\n")
            for m in missing:
                lines.append(f"- `{m}`")

        return "\n".join(lines)

    def _section_recommendations(self) -> str:
        recs = self._generate_recommendations()
        if not recs:
            return "\n## Recomendacoes\n\nNenhum problema critico encontrado.\n"

        lines = ["\n## Recomendacoes Priorizadas\n"]
        for i, rec in enumerate(recs, 1):
            priority = rec.get("priority", "MEDIA")
            title = rec.get("title", "")
            desc = rec.get("description", "")
            action = rec.get("action", "")
            lines.append(f"### {i}. [{priority}] {title}")
            lines.append(f"{desc}")
            if action:
                lines.append(f"\n**Acao:** {action}\n")
            else:
                lines.append("")

        return "\n".join(lines)

    def _score_bar(self, score: int) -> str:
        filled = round(score / 2)
        return "[" + "#" * filled + "-" * (5 - filled) + "]"

    def _finding_meta(self, finding: Dict[str, Any], score: int) -> Dict[str, str]:
        severity = str(finding.get("severity", "MEDIA")).upper()
        impact_map = {
            "ALTA": "Alto impacto",
            "MEDIA": "Impacto moderado",
            "BAIXA": "Impacto baixo",
        }
        confidence_map = {
            "ALTA": "Alta",
            "MEDIA": "Média",
            "BAIXA": "Baixa",
        }
        if score >= 8:
            confidence = "Alta"
        elif score >= 6:
            confidence = "Média"
        else:
            confidence = "Baixa"
        return {
            "impact": impact_map.get(severity, "Impacto moderado"),
            "confidence": confidence_map.get(severity, confidence),
        }

    def _inline_text(self, value: Any, limit: int = 90) -> str:
        text = str(value).replace("|", "\\|").replace("\n", " ").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def _generate_action_summary(self, recs: List[Dict]) -> Dict[str, Any]:
        top_actions = recs[:3]
        manual_review = [rec for rec in recs if rec.get("manual_review")]
        quick_win = next(
            (rec for rec in recs if rec.get("priority") == "ALTA" and not rec.get("manual_review")),
            None,
        )

        return {
            "total_actions": len(recs),
            "top_actions": top_actions,
            "manual_review": manual_review,
            "quick_win": quick_win,
        }

    def _generate_recommendations(self) -> List[Dict]:
        recs = []
        criteria = self.analysis.get("criteria", {})

        for key, value in criteria.items():
            score = value.get("score", 10)
            findings = value.get("findings", [])
            first_finding = findings[0] if findings else {}
            suggestion = first_finding.get("suggestion", "")
            severity = str(value.get("severity", "MEDIA")).upper()
            manual_review = score < 7 and not suggestion

            if score < 5:
                recs.append({
                    "title": key,
                    "description": (
                        f"Score {score}/10 - {len(findings)} problema(s) critico(s). "
                        f"Refatoracao urgente necessaria."
                    ),
                    "priority": "ALTA",
                    "impact": "Alto impacto",
                    "confidence": "Alta",
                    "next_step": suggestion or f"Revisar {key} e aplicar correcoes estruturais.",
                    "why_now": (
                        f"{len(findings)} finding(s) com score abaixo de 5 "
                        f"e risco alto para manutencao."
                    ),
                    "action": suggestion,
                    "score": score,
                    "finding_count": len(findings),
                    "manual_review": manual_review,
                })
            elif score < 7:
                recs.append({
                    "title": key,
                    "description": (
                        f"Score {score}/10 - {len(findings)} problema(s). "
                        f"Oportunidade de melhoria importante."
                    ),
                    "priority": "MEDIA",
                    "impact": "Impacto moderado",
                    "confidence": "Media" if severity == "MEDIA" else "Alta",
                    "next_step": suggestion or f"Validar {key} e reduzir a complexidade detectada.",
                    "why_now": (
                        f"O criterio ainda está fora do intervalo desejado e "
                        f"pode virar problema recorrente."
                    ),
                    "action": suggestion,
                    "score": score,
                    "finding_count": len(findings),
                    "manual_review": manual_review,
                })

        tests = self.analysis.get("test_analysis", {})
        missing = tests.get("missing_tests", [])
        if len(missing) > 3:
            recs.append({
                "title": "Cobertura de Testes",
                "description": f"{len(missing)} metodos sem testes detectados.",
                "priority": "MEDIA",
                "impact": "Impacto moderado",
                "confidence": "Alta",
                "next_step": f"Adicione testes para: {', '.join(missing[:3])}...",
                "why_now": (
                    f"{len(missing)} pontos sem cobertura reduzem a confiança "
                    f"para refatorar ou evoluir o codigo."
                ),
                "action": f"Adicione testes para: {', '.join(missing[:3])}...",
                "score": max(0, 7 - min(len(missing), 4)),
                "finding_count": len(missing),
                "manual_review": False,
            })

        order = {"ALTA": 0, "MEDIA": 1, "BAIXA": 2}
        recs.sort(
            key=lambda x: (
                order.get(x.get("priority", "BAIXA"), 3),
                x.get("score", 10),
                -x.get("finding_count", 0),
                x.get("title", ""),
            )
        )
        return recs

    def save_reports(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        try:
            if output_dir is not None:
                self.artifacts = ArtifactRegistry(
                    self.filepath,
                    output_dir=output_dir,
                    structured_outputs=True,
                )

            json_path = self.artifacts.path_for("analysis", f"{self.filepath.stem}_analysis.json")
            json_report = self.generate_json_report()
            json_payload = json.dumps(json_report, indent=2, default=str, ensure_ascii=False)
            self._write_text_atomic(json_path, json_payload)
            self.artifacts.record(
                "analysis",
                json_path,
                description="Relatorio JSON estruturado da analise",
            )

            md_path = self.artifacts.path_for("report", f"{self.filepath.stem}_report.md")
            md_report = self.generate_markdown_report()
            self._write_text_atomic(md_path, md_report)
            self.artifacts.record(
                "report",
                md_path,
                description="Relatorio Markdown com evidencias e proximas acoes",
            )

            manifest_path = self.artifacts.save_manifest(
                {
                    "analysis_file": str(json_path),
                    "report_file": str(md_path),
                }
            )

            return {
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "manifest": str(manifest_path),
            }
        except Exception as exc:
            log_path = self.artifacts.path_for("log", "report_generation_error.log")
            log_payload = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            try:
                self._write_text_atomic(log_path, log_payload)
                self.artifacts.record(
                    "log",
                    log_path,
                    status="error",
                    description="Falha ao gerar relatórios",
                    metadata={"error": str(exc)},
                )
            except Exception:
                pass
            return {"error": f"Erro ao gerar relatorios: {exc}", "log_file": str(log_path)}


def generate_reports(
    filepath: str,
    analysis: Dict[str, Any],
    output_dir: Optional[str] = None,
    artifact_registry: Optional[ArtifactRegistry] = None,
) -> Dict[str, str]:
    try:
        generator = ReportGenerator(
            filepath,
            analysis,
            artifact_registry=artifact_registry,
            output_dir=output_dir,
        )
        return generator.save_reports(None if artifact_registry else output_dir)
    except Exception as e:
        return {"error": f"Erro ao gerar relatorios: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python report_generator.py <arquivo.py>")
        sys.exit(1)

    dummy = {
        "metrics": {
            "lines_of_code": 100, "code_lines": 80,
            "comment_lines": 10, "blank_lines": 10,
            "num_classes": 2, "num_functions": 5,
            "num_imports": 3, "avg_cyclomatic_complexity": 2.0,
            "max_cyclomatic_complexity": 5,
            "maintainability_index": 72.0,
            "maintainability_grade": "B (Good)",
            "comment_ratio": 12.5
        },
        "criteria": {}
    }
    result = generate_reports(sys.argv[1], dummy)
    print(json.dumps(result, indent=2, ensure_ascii=False))
