"""Report generator — JSON, Markdown, and HTML dashboard outputs."""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer._version import __version__
from code_analyzer.analyzer import prune_criteria
from code_analyzer.artifact_manager import ArtifactRegistry
from code_analyzer.constants import CRITERIA_WEIGHT, MI_WEIGHT
from code_analyzer.limits import (
    MAX_MISSING_TESTS_SAMPLE,
    MAX_TOP_RECOMMENDATIONS,
)
from code_analyzer.reporting.html_sections import HtmlSections
from code_analyzer.reporting.markdown_sections import MarkdownSections

_log = logging.getLogger(__name__)

__all__ = ["ReportGenerator", "generate_reports"]


class ReportGenerator:
    """Generates structured reports with per-line details and suggestions."""

    GRADE_COLORS = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}
    SEVERITY_COLORS = {"ALTA": "#ef4444", "MEDIA": "#f59e0b", "BAIXA": "#3b82f6"}

    def __init__(
        self,
        filepath: str,
        analysis: Dict[str, Any],
        artifact_registry: Optional[ArtifactRegistry] = None,
        output_dir: Optional[str] = None,
        structured_outputs: bool = True,
    ) -> None:
        self.filepath = Path(filepath)
        self.analysis = analysis
        self.timestamp = datetime.now().isoformat()
        self.lines = self._load_source_lines()
        self.compact = analysis.get("config", {}).get("compact", False)
        self.artifacts = artifact_registry or ArtifactRegistry(
            self.filepath,
            output_dir=output_dir,
            structured_outputs=structured_outputs,
        )
        self._md = MarkdownSections(self)
        self._html = HtmlSections(self)

    def _load_source_lines(self) -> List[str]:
        try:
            return self.filepath.read_text(encoding="utf-8").split("\n")
        except (OSError, UnicodeDecodeError):
            _log.warning("Failed to read source lines from %s", self.filepath, exc_info=True)
            return []

    def _write_text_atomic(self, path: Path, content: str) -> None:
        if not content or not content.strip():
            raise ValueError(f"Empty content for artifact: {path.name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    def _get_snippet(self, lineno: int, context: int = 2) -> str:
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
                "tool": f"Code Architecture Analyzer v{__version__}",
                "version": __version__,
                "output_root": str(self.artifacts.run_root),
                "analysis_dir": str(self.artifacts.analysis_dir),
                "reports_dir": str(self.artifacts.reports_dir),
            },
            "summary": self._generate_summary(),
            "metrics": self.analysis.get("metrics", {}),
            "criteria": prune_criteria(self.analysis).get("criteria", {}),
            "dependencies": self.analysis.get("dependencies", {}),
            "test_analysis": self.analysis.get("test_analysis", {}),
            "test_practices": self.analysis.get("test_practices", {}),
            "tool_findings": self.analysis.get("tool_findings", {}),
            "config": self.analysis.get("config", {}),
            "action_summary": self._generate_action_summary(recommendations),
            "recommendations": recommendations,
        }

    def generate_markdown_report(self) -> str:
        parts = [
            f"# Relatorio de Analise de Arquitetura - {self.filepath.name}",
            f"\n**Data:** {self.timestamp}",
            f"**Arquivo:** `{self.filepath}`",
            f"**Ferramenta:** Code Architecture Analyzer v{__version__}\n",
            self._md.section_priority_index(),
            self._md.section_equivalence(),
            self._md.section_semantic(),
            self._md.section_project_context(),
            self._md.section_pattern_advisor(),
            self._md.section_summary(),
            self._md.section_action_plan(),
            self._md.section_metrics(),
            self._md.section_criteria(),
            self._md.section_dependencies(),
            self._md.section_tools(),
            self._md.section_tests(),
            self._md.section_test_pain(),
            self._md.section_test_practices(),
            self._md.section_recommendations(),
            self._md.section_history(),
        ]
        return "\n".join(parts)

    def generate_html_report(self) -> str:
        return self._html.generate_html_report()

    def _generate_summary(self) -> Dict[str, Any]:
        criteria = self.analysis.get("criteria", {})
        scores = [v.get("score", 0) for v in criteria.values()]
        criteria_avg = round(sum(scores) / max(1, len(scores)), 1)
        mi = self.analysis.get("metrics", {}).get("maintainability_index", 0)
        mi_component = min(10.0, mi / 10.0)
        avg = round(criteria_avg * CRITERIA_WEIGHT + mi_component * MI_WEIGHT, 1)

        security_penalty = 0.0
        for k, v in criteria.items():
            if k in ("InjectionRisk", "HardcodedSecrets", "MassAssignment"):
                security_penalty += len(v.get("findings", [])) * 1.5
        adjusted = round(max(0.0, avg - security_penalty), 1)

        findings_count = sum(len(v.get("findings", [])) for v in criteria.values())

        risk = self.analysis.get("production_risk", {})
        return {
            "overall_score": adjusted,
            "raw_score": avg,
            "security_penalty": security_penalty,
            "grade": self._score_to_grade(adjusted),
            "critical_criteria": [k for k, v in criteria.items() if v.get("score", 10) < 5],
            "warning_criteria": [k for k, v in criteria.items() if 5 <= v.get("score", 10) < 7],
            "total_findings": findings_count,
            "maintainability_grade": self.analysis.get("metrics", {}).get("maintainability_grade", "N/A"),
            "production_risk": risk,
            "test_pain": self.analysis.get("test_pain", {}).get("aggregate", 0),
        }

    def _score_to_grade(self, score: float) -> str:
        if score >= 9:
            return "A"
        if score >= 7:
            return "B"
        if score >= 5:
            return "C"
        return "D"

    def _generate_action_summary(self, recs: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "total_actions": len(recs),
            "top_actions": recs[:MAX_TOP_RECOMMENDATIONS],
            "manual_review": [r for r in recs if r.get("manual_review")],
            "quick_win": next(
                (r for r in recs if r.get("priority") == "ALTA" and not r.get("manual_review")), None
            ),
        }

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        criteria = self.analysis.get("criteria", {})
        for key, value in criteria.items():
            score = value.get("score", 10)
            findings = value.get("findings", [])
            suggestion = findings[0].get("suggestion", "") if findings else ""
            manual_review = score < 7 and not suggestion
            if score < 5:
                recs.append({
                    "title": key,
                    "description": f"Score {score}/10 - {len(findings)} problema(s) critico(s). Refatoracao urgente necessaria.",
                    "priority": "ALTA",
                    "impact": "Alto impacto",
                    "confidence": "Alta",
                    "next_step": suggestion or f"Revisar {key} e aplicar correcoes estruturais.",
                    "why_now": f"{len(findings)} finding(s) com score abaixo de 5 e risco alto para manutencao.",
                    "action": suggestion,
                    "score": score,
                    "finding_count": len(findings),
                    "manual_review": manual_review,
                })
            elif score < 7:
                recs.append({
                    "title": key,
                    "description": f"Score {score}/10 - {len(findings)} problema(s). Oportunidade de melhoria importante.",
                    "priority": "MEDIA",
                    "impact": "Impacto moderado",
                    "confidence": "Media",
                    "next_step": suggestion or f"Validar {key} e reduzir a complexidade detectada.",
                    "why_now": "O criterio ainda esta fora do intervalo desejado e pode virar problema recorrente.",
                    "action": suggestion,
                    "score": score,
                    "finding_count": len(findings),
                    "manual_review": manual_review,
                })
        tests = self.analysis.get("test_analysis", {})
        missing = tests.get("missing_tests", [])
        if len(missing) > MAX_MISSING_TESTS_SAMPLE:
            sample = ", ".join(missing[:MAX_MISSING_TESTS_SAMPLE])
            recs.append({
                "title": "Cobertura de Testes",
                "description": f"{len(missing)} metodos sem testes detectados.",
                "priority": "MEDIA",
                "impact": "Impacto moderado",
                "confidence": "Alta",
                "next_step": f"Adicione testes para: {sample}...",
                "why_now": f"{len(missing)} pontos sem cobertura reduzem a confianca para refatorar.",
                "action": f"Adicione testes para: {sample}...",
                "score": max(0, 7 - min(len(missing), 4)),
                "finding_count": len(missing),
                "manual_review": False,
            })
        order = {"ALTA": 0, "MEDIA": 1, "BAIXA": 2}
        recs.sort(key=lambda x: (order.get(x.get("priority", "BAIXA"), 3), x.get("score", 10), -x.get("finding_count", 0), x.get("title", "")))
        return recs

    def save_reports(self, output_dir: Optional[str] = None, generate_html: bool = False, html_only: bool = False) -> Dict[str, str]:
        if html_only:
            html_dir = Path(output_dir) if output_dir else (Path.home() / ".code-analyzer" / "reports")
            try:
                html_dir.mkdir(parents=True, exist_ok=True)
                html_path = html_dir / f"{self.filepath.stem}_dashboard.html"
                self._write_text_atomic(html_path, self.generate_html_report())
                return {"html_report": str(html_path)}
            except OSError as exc:
                return {"error": f"Erro ao gerar HTML: {exc}"}
        try:
            if output_dir is not None:
                self.artifacts = ArtifactRegistry(self.filepath, output_dir=output_dir, structured_outputs=True)

            json_path = self.artifacts.path_for("analysis", f"{self.filepath.stem}_analysis.json")
            json_payload = json.dumps(self.generate_json_report(), indent=2, default=str, ensure_ascii=False)
            self._write_text_atomic(json_path, json_payload)
            self.artifacts.record("analysis", json_path, description="Relatorio JSON estruturado da analise")

            md_path = self.artifacts.path_for("report", f"{self.filepath.stem}_report.md")
            self._write_text_atomic(md_path, self.generate_markdown_report())
            self.artifacts.record("report", md_path, description="Relatorio Markdown com evidencias e proximas acoes")

            result: Dict[str, str] = {
                "analysis_file": str(json_path),
                "report_file": str(md_path),
                "json_report": str(json_path),
                "markdown_report": str(md_path),
            }

            if generate_html:
                html_path = self.artifacts.path_for("report", f"{self.filepath.stem}_dashboard.html")
                self._write_text_atomic(html_path, self.generate_html_report())
                self.artifacts.record("report", html_path, description="Dashboard HTML visual para apresentacao")
                result["html_report"] = str(html_path)

            manifest_path = self.artifacts.save_manifest(result)
            result["manifest"] = str(manifest_path)
            return result
        except Exception as exc:  # broad: covers JSON/HTML generation + file I/O
            log_path = self.artifacts.path_for("log", "report_generation_error.log")
            log_payload = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            try:
                self._write_text_atomic(log_path, log_payload)
                self.artifacts.record("log", log_path, status="error", description="Falha ao gerar relatorios", metadata={"error": str(exc)})
            except OSError:
                _log.error("Failed to write error log for report generation", exc_info=True)
            return {"error": f"Erro ao gerar relatorios: {exc}", "log_file": str(log_path)}


def generate_reports(
    filepath: str,
    analysis: Dict[str, Any],
    output_dir: Optional[str] = None,
    artifact_registry: Optional[ArtifactRegistry] = None,
    generate_html: bool = False,
    html_only: bool = False,
) -> Dict[str, str]:
    try:
        generator = ReportGenerator(filepath, analysis, artifact_registry=artifact_registry, output_dir=output_dir)
        return generator.save_reports(
            None if artifact_registry else output_dir,
            generate_html=generate_html,
            html_only=html_only,
        )
    except Exception as exc:  # wraps entire report generation
        return {"error": f"Erro ao gerar relatorios: {exc}"}
