"""Report generator — JSON, Markdown, and HTML dashboard outputs."""
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

from code_analyzer import __version__
from code_analyzer.analyzer import prune_criteria
from code_analyzer.artifact_manager import ArtifactRegistry
from code_analyzer.history import load_history
from code_analyzer.pattern_advisor import get_pattern_advice
from code_analyzer.project_context import compute_priority_index
from code_analyzer.limits import (
    MAX_CYCLES_LISTED,
    MAX_FINDINGS_PER_DETECTOR,
    MAX_MISSING_TESTS_SAMPLE,
    MAX_REPORT_TOP_ITEMS,
    MAX_TOP_RECOMMENDATIONS,
)
import html as _html


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

    def _load_source_lines(self) -> List[str]:
        try:
            return self.filepath.read_text(encoding="utf-8").split("\n")
        except Exception:
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
            self._section_priority_index(),
            self._section_equivalence(),
            self._section_project_context(),
            self._section_pattern_advisor(),
            self._section_summary(),
            self._section_action_plan(),
            self._section_metrics(),
            self._section_criteria(),
            self._section_dependencies(),
            self._section_tools(),
            self._section_tests(),
            self._section_test_pain(),
            self._section_recommendations(),
            self._section_history(),
        ]
        return "\n".join(parts)

    def _section_history(self) -> str:
        snapshots = load_history(str(self.filepath))
        if not snapshots:
            return ""
        lines = [
            "\n## Historico de Evolucao\n",
            "| Execucao | MI | Grade | Criterios com problemas |",
            "|---|---|---|---|",
        ]
        # Mostrar os últimos 5 runs
        for s in snapshots[-5:]:
            ts = s.get("timestamp", "")[:19].replace("T", " ")
            mi = s.get("maintainability_index", 100.0)
            grade = s.get("maintainability_grade", "A")
            problems = []
            for k, v in s.get("scores", {}).items():
                if v < 10.0:
                    problems.append(f"{k} ({v:.1f})")
            problems_str = ", ".join(problems) if problems else "Nenhum"
            lines.append(f"| {ts} | {int(mi)} | {grade} | {problems_str} |")
        return "\n".join(lines)

    def generate_html_report(self) -> str:
        summary = self._generate_summary()
        metrics = self.analysis.get("metrics", {})
        criteria = self.analysis.get("criteria", {})
        deps = self.analysis.get("dependencies", {})
        tests = self.analysis.get("test_analysis", {})
        recs = self._generate_recommendations()
        tool_findings = self.analysis.get("tool_findings", {})

        grade_color = self.GRADE_COLORS.get(summary["grade"], "#6b7280")
        grouped: Dict[str, List] = {"ALTA": [], "MEDIA": [], "BAIXA": []}
        for k, v in criteria.items():
            sev = v.get("severity", "MEDIA").upper()
            if sev in grouped:
                grouped[sev].append((k, v))

        def esc(t: str) -> str:
            return _html.escape(str(t))

        # Gerar bloco de histórico HTML
        snapshots = load_history(str(self.filepath))
        history_html = ""
        if snapshots:
            history_row_parts = []
            for s in snapshots[-5:]:
                ts = esc(s.get("timestamp", "")[:19].replace("T", " "))
                mi = int(s.get("maintainability_index", 100.0))
                grade = esc(s.get("maintainability_grade", "A"))
                problems = []
                for k, v in s.get("scores", {}).items():
                    if v < 10.0:
                        problems.append(f"{esc(k)} ({v:.1f})")
                problems_str = ", ".join(problems) if problems else "Nenhum"
                history_row_parts.append(f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>{ts}</td><td style='padding: 8px; border: 1px solid #ddd;'>{mi}</td><td style='padding: 8px; border: 1px solid #ddd;'>{grade}</td><td style='padding: 8px; border: 1px solid #ddd;'>{problems_str}</td></tr>")
            history_rows = "".join(history_row_parts)
            
            history_html = f'''
            <h2>📈 Histórico de Evolução</h2>
            <table class="history-table" style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-family: sans-serif;">
                <thead>
                    <tr style="background-color: #f3f4f6; text-align: left; border-bottom: 2px solid #e5e7eb;">
                        <th style="padding: 10px; border: 1px solid #ddd;">Execução (Data/Hora)</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">MI</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Grade</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Critérios com problemas (Score &lt; 10)</th>
                    </tr>
                </thead>
                <tbody>
                    {history_rows}
                </tbody>
            </table>
            '''

        def score_bar(s: int) -> str:
            w = max(0, min(100, s * 10))
            color = "#22c55e" if s >= 7 else ("#f59e0b" if s >= 5 else "#ef4444")
            return f'<div class="sb"><div class="sb-f" style="width:{w}%;background:{color}"></div></div>'

        def cards_html(items: list, title: str) -> str:
            if not items:
                return ""
            row_parts = []
            for name, val in items:
                s = val.get("score", 0)
                findings = val.get("findings", [])
                detail_parts = []
                for f in findings:
                    loc = esc(f.get("location", ""))
                    iss = esc(f.get("issue", ""))
                    sug = esc(f.get("suggestion", ""))
                    ct = esc(f.get("line_content", ""))
                    detail_parts.append(f'<div class="finding"><span class="loc">[{loc}]</span> {iss}')
                    if ct:
                        detail_parts.append(f"<pre>{ct}</pre>")
                    if sug:
                        detail_parts.append(f'<div class="sug">💡 {sug}</div>')
                    detail_parts.append("</div>")
                details = "".join(detail_parts)
                cls = "ok" if s >= 7 else "warn" if s >= 5 else "crit"
                row_parts.append(
                    f'<div class="card card-{cls}">'
                    f'<div class="card-h"><span class="card-t">{esc(name)}</span>'
                    f'<span class="card-sc">{s}/10</span></div>'
                    f"{score_bar(s)}"
                    f'<div class="card-sev">{esc(val.get("description",""))}</div>'
                    + (f'<div class="card-n">{len(findings)} problema(s)</div>' if findings else '<div class="card-n ok">✓ Sem problemas</div>')
                    + details
                    + "</div>"
                )
            rows = "".join(row_parts)
            return f"<h2>{esc(title)}</h2><div class=\"grid\">{rows}</div>" if rows else ""

        rec_parts = []
        for i, r in enumerate(recs[:MAX_REPORT_TOP_ITEMS], 1):
            p = esc(r.get("priority", "MEDIA"))
            t = esc(r.get("title", ""))
            d = esc(r.get("description", ""))
            a = esc(r.get("action", ""))
            pc = "al" if p == "ALTA" else "me" if p == "MEDIA" else "ba"
            rec_parts.append(
                f'<div class="rec {pc}"><span class="rec-badge {pc}">{p}</span>'
                f"<strong>{t}</strong><p>{d}</p>"
                + (f'<div class="rec-a">➜ {a}</div>' if a else "")
                + "</div>"
            )
        rec_block = "".join(rec_parts)

        criteria_keys_ok = [k for k, v in criteria.items() if v.get("score", 10) >= 7]
        criteria_keys_warn = [k for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]
        criteria_keys_crit = [k for k, v in criteria.items() if v.get("score", 10) < 5]

        deps_parts = []
        if deps:
            tpi = deps.get("third_party", [])
            crc = deps.get("circular_dependencies", [])
            dup = deps.get("duplicate_imports", [])
            deps_parts.append(f'<div class="m-card"><strong>Imports:</strong> {deps.get("total_imports",0)} total, {deps.get("unique_modules",0)} unicos</div>')
            if tpi:
                deps_parts.append(f'<div class="m-card"><strong>Externos:</strong> {" ".join(esc(x) for x in tpi)}</div>')
            for c in crc[:MAX_REPORT_TOP_ITEMS]:
                pth = " -> ".join(c) if isinstance(c, list) else str(c)
                deps_parts.append(f'<div class="m-card crit"><strong>Circular:</strong> {esc(pth)}</div>')
            for d in dup[:MAX_REPORT_TOP_ITEMS]:
                deps_parts.append(f'<div class="m-card warn"><strong>Duplicado:</strong> {esc(d.get("module",""))} (linha {d.get("lineno","?")})</div>')
        deps_lines = "".join(deps_parts) if deps_parts else '<div class="m-card">Nenhuma dependencia analisada.</div>'

        if tests:
            cov = tests.get("estimated_coverage", 0)
            cov_color = "#22c55e" if cov >= 50 else "#f59e0b" if cov >= 20 else "#ef4444"
            missing = tests.get("missing_tests", [])
            tests_parts = [
                f'<div class="m-card"><strong>Testes:</strong> {tests.get("test_functions",0)} funcoes, {tests.get("test_classes",0)} classes</div>',
                f'<div class="m-card"><strong>Cobertura estimada:</strong> <span style="color:{cov_color};font-weight:bold">{cov}%</span></div>',
                f'<div class="m-card"><strong>pytest:</strong> {"Sim" if tests.get("uses_pytest") else "Nao"}</div>',
            ]
            if missing:
                tests_parts.append(
                    f'<div class="m-card warn"><strong>Sem teste ({len(missing)}):</strong> '
                    f'{" ".join(esc(m) for m in missing[:MAX_REPORT_TOP_ITEMS])}</div>'
                )
            tests_lines = "".join(tests_parts)
        else:
            tests_lines = '<div class="m-card">Nenhuma analise de testes disponivel.</div>'

        tool_parts = []
        if tool_findings.get("total", 0):
            for tn in ["ruff"]:
                fts = tool_findings.get(tn, [])
                if fts:
                    items_html = "".join(
                        f'<li><code>{esc(f.get("code",""))}</code> — {esc(f.get("issue",""))[:80]}</li>'
                        for f in fts[:8]
                    )
                    tool_parts.append(f'<div class="m-card"><strong>{tn}:</strong> {len(fts)} ocorrencias<ul>{items_html}</ul></div>')
        for w in self.analysis.get("tool_warnings", []):
            tool_parts.append(
                f'<div class="m-card warn" style="border-left:4px solid #ef4444;background:#fef2f2;color:#991b1b;margin-bottom:10px">'
                f'<strong>⚠ Analise Parcial:</strong> {esc(w)}.<br>'
                f'Execute <code>code-analyze setup</code> no terminal para instalar ferramentas ausentes.</div>'
            )
        tool_block = "".join(tool_parts)

        # Score disclaimer
        score_disclaimer_html = (
            '<div style="background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #f59e0b;'
            'border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:.82rem;color:#78350f;">'
            '<strong>Escopo do score:</strong> mede convenções estruturais e anti-patterns detectáveis '
            'estaticamente (SOLID, complexidade, acoplamento). '
            'Bugs semânticos — lógica de negócio incorreta, comportamento inesperado de ORM, '
            'race conditions — <strong>não são detectados automaticamente</strong>. '
            'Um score alto não garante ausência de bugs funcionais.</div>'
        )

        # Project context block
        pctx = self.analysis.get("project_context", {})
        project_context_html = ""
        if pctx.get("found"):
            debt_items = "".join(
                f"<li>{esc(d)}</li>" for d in pctx.get("known_debts", [])
            )
            mention_badge = (
                f'<div style="background:#fef2f2;color:#991b1b;padding:6px 10px;'
                f'border-radius:6px;margin-bottom:8px;font-size:.82rem;">'
                f'<strong>⚠ Este arquivo é mencionado no CLAUDE.md</strong> — '
                f'verifique se há débitos ou bugs conhecidos relativos a <code>{esc(self.filepath.name)}</code>.</div>'
            ) if pctx.get("file_mentioned") else ""
            debt_block = (
                f'<strong>Indicadores de débito técnico no CLAUDE.md:</strong>'
                f'<ul style="margin:6px 0 0 16px;font-size:.82rem;color:#475569;">{debt_items}</ul>'
            ) if debt_items else ""
            project_context_html = (
                f'<h2>📋 Contexto do Projeto (CLAUDE.md)</h2>'
                f'<div class="m-card" style="margin-bottom:16px;">'
                f'{mention_badge}{debt_block}'
                f'<div style="font-size:.75rem;color:#94a3b8;margin-top:6px;">Fonte: {esc(pctx.get("path","CLAUDE.md"))}</div>'
                f'</div>'
            )

        overall = summary["overall_score"]
        risk = summary.get("production_risk", {})
        risk_score = risk.get("score", 0)
        risk_label = risk.get("label", "N/A")
        risk_cls = "crit" if risk_label == "Critico" else "warn" if risk_label == "Risco" else "ok"
        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analyzer - {esc(self.filepath.name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f1f5f9;color:#1e293b;line-height:1.6;padding:20px}}
.container{{max-width:1200px;margin:0 auto}}
.hero{{background:linear-gradient(135deg,{grade_color}22,{grade_color}44);border-radius:16px;padding:30px;margin-bottom:24px;text-align:center;border:1px solid {grade_color}44}}
.hero h1{{font-size:1.4rem;color:#475569;margin-bottom:8px}}
.hero .score{{font-size:4rem;font-weight:800;color:{grade_color};line-height:1}}
.hero .grade{{display:inline-block;background:{grade_color};color:#fff;border-radius:50%;width:48px;height:48px;line-height:48px;font-size:1.5rem;font-weight:700;margin:8px auto}}
.hero .meta{{color:#64748b;font-size:.9rem;margin-top:8px}}
.badges{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin:16px 0}}
.badge{{padding:8px 16px;border-radius:8px;font-size:.85rem;font-weight:600}}
.badge.crit{{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}}
.badge.warn{{background:#fffbeb;color:#d97706;border:1px solid #fde68a}}
.badge.ok{{background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}}
h2{{font-size:1.1rem;color:#334155;margin:24px 0 12px;padding-bottom:6px;border-bottom:2px solid #e2e8f0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}}
.card{{background:#fff;border-radius:10px;padding:14px;border:1px solid #e2e8f0;transition:box-shadow .15s}}
.card:hover{{box-shadow:0 4px 12px #00000012}}
.card-h{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.card-t{{font-weight:600;font-size:.95rem}}
.card-sc{{font-weight:700;font-size:.9rem}}
.card.crit{{border-left:4px solid #ef4444}}
.card.warn{{border-left:4px solid #f59e0b}}
.card.ok{{border-left:4px solid #22c55e}}
.card-sev{{font-size:.8rem;color:#64748b;margin:4px 0}}
.card-n{{font-size:.8rem;font-weight:600;color:#dc2626;margin:4px 0}}
.card-n.ok{{color:#16a34a}}
.sb{{height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin:6px 0}}
.sb-f{{height:100%;border-radius:3px;transition:width .4s}}
.finding{{background:#f8fafc;padding:8px;border-radius:6px;margin:6px 0 0;font-size:.82rem;border:1px solid #e2e8f0;word-wrap:break-word}}
.finding .loc{{color:#64748b}}
.finding pre{{background:#f1f5f9;padding:4px 8px;border-radius:4px;font-size:.78rem;margin:4px 0;overflow-x:auto;white-space:pre-wrap}}
.sug{{color:#059669;margin-top:2px;font-size:.8rem}}
.rec{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:8px}}
.rec.al{{border-left:4px solid #ef4444}}
.rec.me{{border-left:4px solid #f59e0b}}
.rec.ba{{border-left:4px solid #3b82f6}}
.rec-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:700;margin-right:8px}}
.rec-badge.al{{background:#fef2f2;color:#dc2626}}
.rec-badge.me{{background:#fffbeb;color:#d97706}}
.rec-badge.ba{{background:#eff6ff;color:#2563eb}}
.rec p{{font-size:.85rem;color:#475569;margin:4px 0}}
.rec-a{{font-size:.85rem;color:#059669;font-weight:600;margin-top:4px}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}}
.m-card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;font-size:.85rem}}
.m-card.crit{{border-left:3px solid #ef4444}}
.m-card.warn{{border-left:3px solid #f59e0b}}
.m-card ul{{margin:4px 0 0 16px;font-size:.8rem;color:#475569}}
.footer{{text-align:center;color:#94a3b8;font-size:.75rem;margin-top:32px;padding:16px 0;border-top:1px solid #e2e8f0}}
@media(max-width:640px){{.grid{{grid-template-columns:1fr}}.hero .score{{font-size:3rem}}}}
</style></head>
<body><div class="container">
<div class="hero">
<h1>📊 {esc(self.filepath.name)}</h1>
<div class="score">{overall}</div>
<div class="grade">{summary["grade"]}</div>
<div class="meta">{esc(str(self.filepath))} &middot; {esc(self.timestamp[:10])}</div>
<div class="badges">
<span class="badge crit">🔴 {len(criteria_keys_crit)} Criticos</span>
<span class="badge warn">🟡 {len(criteria_keys_warn)} Avisos</span>
<span class="badge ok">🟢 {len(criteria_keys_ok)} OK</span>
<span class="badge">{summary["total_findings"]} Findings</span>
<span class="badge {risk_cls}">Risco: {risk_score}/100 ({risk_label})</span>
<span class="badge">{metrics.get("maintainability_grade","N/A")}</span>
</div></div>

{score_disclaimer_html}
{project_context_html}
{cards_html(grouped.get("ALTA",[]),"🔴 Alta Severidade")}
{cards_html(grouped.get("MEDIA",[]),"🟡 Media Severidade")}
{cards_html(grouped.get("BAIXA",[]),"🔵 Baixa Severidade")}

<h2>📈 Metricas de Codigo</h2>
<div class="metrics">
<div class="m-card"><strong>Linhas:</strong> {metrics.get("lines_of_code",0)} ({metrics.get("code_lines",0)} codigo)</div>
<div class="m-card"><strong>Comentarios:</strong> {metrics.get("comment_ratio",0)}% (alvo {metrics.get("comment_ratio_target",10)}%)</div>
<div class="m-card"><strong>Classes:</strong> {metrics.get("num_classes",0)}</div>
<div class="m-card"><strong>Funcoes:</strong> {metrics.get("num_functions",0)}</div>
<div class="m-card"><strong>Complex. media:</strong> {metrics.get("avg_cyclomatic_complexity",0)}</div>
<div class="m-card"><strong>Complex. maxima:</strong> {metrics.get("max_cyclomatic_complexity",0)}</div>
<div class="m-card"><strong>MI:</strong> {metrics.get("maintainability_index",0)} ({metrics.get("maintainability_grade","N/A")})</div>
</div>

<h2>🔗 Dependencias</h2>
<div class="metrics">{deps_lines}</div>

<h2>🧪 Testes</h2>
<div class="metrics">{tests_lines}</div>

{f'<h2>🔧 Ferramentas Externas</h2><div class="metrics">{tool_block}</div>' if tool_block else ''}

{f'<h2>🎯 Recomendacoes</h2>{rec_block}' if recs else ''}

{history_html}

<div class="footer">Code Architecture Analyzer v{__version__} &middot; {esc(self.timestamp)}</div>
</div></body></html>'''

    def _generate_summary(self) -> Dict[str, Any]:
        criteria = self.analysis.get("criteria", {})
        scores = [v.get("score", 0) for v in criteria.values()]
        criteria_avg = round(sum(scores) / max(1, len(scores)), 1)
        mi = self.analysis.get("metrics", {}).get("maintainability_index", 0)
        mi_component = min(10.0, mi / 10.0)
        avg = round(criteria_avg * 0.7 + mi_component * 0.3, 1)
        risk = self.analysis.get("production_risk", {})
        return {
            "overall_score": avg,
            "grade": self._score_to_grade(avg),
            "critical_criteria": [k for k, v in criteria.items() if v.get("score", 10) < 5],
            "warning_criteria": [k for k, v in criteria.items() if 5 <= v.get("score", 10) < 7],
            "total_findings": sum(len(v.get("findings", [])) for v in criteria.values()),
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

    def _score_bar(self, score: int) -> str:
        filled = round(score / 2)
        return "[" + "#" * filled + "-" * (5 - filled) + "]"

    def _finding_meta(self, finding: Dict[str, Any], score: int) -> Dict[str, str]:
        severity = str(finding.get("severity", "MEDIA")).upper()
        impact_map = {"ALTA": "Alto impacto", "MEDIA": "Impacto moderado", "BAIXA": "Impacto baixo"}
        confidence = "Alta" if score >= 8 else "Média" if score >= 6 else "Baixa"
        return {"impact": impact_map.get(severity, "Impacto moderado"), "confidence": confidence}

    def _inline_text(self, value: Any, limit: int = 90) -> str:
        text = str(value).replace("|", "\\|").replace("\n", " ").strip()
        return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."

    def _section_priority_index(self) -> str:
        pi = self.analysis.get("priority_index")
        if not pi:
            return ""
        label = pi.get("label", "")
        score = pi.get("score", 0)
        fan_in = pi.get("fan_in", 0)
        commits = pi.get("commit_count", 0)
        coverage = pi.get("coverage_pct", 0)
        badge = {"CRITICO": "🔴", "ALTA": "🟠", "MEDIA": "🟡", "BAIXA": "🟢"}.get(label, "⚪")
        lines = [
            f"\n## Indice de Prioridade Contextual {badge} `{label}` ({score}/100)\n",
            f"| Fator | Valor |",
            f"|-------|-------|",
            f"| Fan-in (arquivos que importam este modulo) | {fan_in} |",
            f"| Commits recentes (90 dias) | {commits} |",
            f"| Cobertura de testes estimada | {coverage}% |",
            f"\n*{pi.get('reason', '')}*\n",
        ]
        return "\n".join(lines)

    def _section_pattern_advisor(self) -> str:
        advice = get_pattern_advice(self.analysis)
        if not advice:
            return ""
        lines = ["\n## Padroes de Projeto Sugeridos\n"]
        for item in advice:
            prio = item["priority"]
            lines.append(f"### {item['pattern']} `[{prio}]`\n")
            lines.append(f"**Sintoma detectado:** {item['symptom']}\n")
            lines.append(f"**Sugestao:** {item['suggestion']}\n")
            involved = ", ".join(f"`{c}`" for c in item.get("criteria_involved", []))
            if involved:
                lines.append(f"*Criterios envolvidos: {involved}*\n")
        return "\n".join(lines)

    def _section_equivalence(self) -> str:
        purity_map = self.analysis.get("purity_map", {})
        if not purity_map:
            return ""
        badge_map = {"pure": "🟢 Alta", "side_effect": "🟡 Média", "unknown": "🔴 Baixa"}
        lines = ["\n## Equivalência de Extração\n"]
        lines.append("| Função | Linhas | Variáveis | Confiança | Motivo |")
        lines.append("|--------|--------|-----------|-----------|--------|")
        for func_name, candidates in purity_map.items():
            for c in candidates:
                purity = c.get("purity", "unknown")
                badge = badge_map.get(purity, "⚪")
                vars_str = ", ".join(c.get("variables", [])[:4])
                reason = "; ".join(c.get("reasons", [])[:2]) or "—"
                lines.append(
                    f"| `{func_name}` | {c['start_line']}–{c['end_line']}"
                    f" | {vars_str} | {badge} | {reason} |"
                )
        lines.append(
            "\n> *Confiança Alta = bloco puro (sem self/I/O). "
            "Média = side-effect, teste de equivalência gerado. "
            "Baixa = revisão manual obrigatória.*\n"
        )
        return "\n".join(lines)

    def _section_project_context(self) -> str:
        ctx = self.analysis.get("project_context", {})
        if not ctx.get("found"):
            return ""
        lines = ["\n## Contexto do Projeto (CLAUDE.md)\n"]
        if ctx.get("file_mentioned"):
            lines.append(f"> **Este arquivo é mencionado no CLAUDE.md** — verifique se há débitos ou bugs conhecidos relativos a `{self.filepath.name}`.\n")
        debts = ctx.get("known_debts", [])
        if debts:
            lines.append("**Linhas com indicadores de débito técnico detectadas no CLAUDE.md:**\n")
            for d in debts:
                lines.append(f"- {d}")
            lines.append("")
        lines.append(f"*Fonte: `{ctx.get('path', 'CLAUDE.md')}`*")
        if ctx.get("truncated"):
            lines.append("*(conteúdo truncado — veja o arquivo completo para contexto adicional)*")
        return "\n".join(lines)

    def _section_summary(self) -> str:
        summary = self._generate_summary()
        risk = summary.get("production_risk", {})
        risk_line = f"| Risco de Producao | {risk.get('score', 0)}/100 ({risk.get('label', 'N/A')}) |"
        lines = [
            "## Resumo Geral\n",
            "| Item | Valor |", "|------|-------|",
            f"| Score Geral | {summary['overall_score']}/10 (Grau {summary['grade']}) |",
            risk_line,
            f"| Manutenibilidade | {summary['maintainability_grade']} |",
            f"| Problemas Criticos | {len(summary['critical_criteria'])} |",
            f"| Avisos | {len(summary['warning_criteria'])} |",
            f"| Total de Findings | {summary['total_findings']} |",
        ]
        if summary["critical_criteria"]:
            lines.append(f"\n**Criticos:** `{'`, `'.join(summary['critical_criteria'])}`")
        if summary["warning_criteria"]:
            lines.append(f"**Avisos:** `{'`, `'.join(summary['warning_criteria'])}`")
        lines.append(
            "\n> **Escopo do score:** mede convenções estruturais e anti-patterns detectáveis "
            "estaticamente (SOLID, complexidade, acoplamento). "
            "Bugs semânticos — lógica de negócio incorreta, comportamento inesperado de ORM, "
            "race conditions — **não são detectados automaticamente**. "
            "Um score alto não garante ausência de bugs funcionais."
        )
        return "\n".join(lines)

    def _section_action_plan(self) -> str:
        recs = self._generate_recommendations()
        if not recs:
            return "\n## Proximas Acoes\n\nNenhuma acao prioritaria encontrada.\n"
        lines = [
            "\n## Proximas Acoes\n",
            "| # | Prioridade | Foco | Impacto | Confianca | Proxima acao |",
            "|---|---|---|---|---|---|",
        ]
        for i, rec in enumerate(recs[:MAX_REPORT_TOP_ITEMS], 1):
            lines.append(
                f"| {i} | {rec.get('priority','MEDIA')} | "
                f"{self._inline_text(rec.get('title',''))} | "
                f"{self._inline_text(rec.get('impact','Impacto moderado'))} | "
                f"{self._inline_text(rec.get('confidence','Media'))} | "
                f"{self._inline_text(rec.get('next_step', rec.get('action','')))} |"
            )
        top = recs[0]
        lines += [
            "", "**Decisao rapida:**",
            f"Comece por `{top.get('title','')}` porque {top.get('why_now', top.get('description',''))}.",
        ]
        if top.get("manual_review"):
            lines.append("Essa acao pede revisao manual antes de aplicar automaticamente.")
        return "\n".join(lines)

    def _section_metrics(self) -> str:
        m = self.analysis.get("metrics", {})
        lines = [
            "\n## Metricas de Codigo\n",
            "| Metrica | Valor |", "|---------|-------|",
            f"| Linhas totais | {m.get('lines_of_code',0)} |",
            f"| Linhas de codigo | {m.get('code_lines',0)} |",
            f"| Linhas de comentario | {m.get('comment_lines',0)} |",
            f"| Ratio comentarios | {m.get('comment_ratio',0)}% |",
        ]
        if "comment_ratio_target" in m:
            lines += [
                f"| Alvo comentarios | {m.get('comment_ratio_target',0)}% |",
                f"| Atingiu alvo | {'Sim' if m.get('comment_ratio_ok') else 'Nao'} |",
            ]
        lines += [
            f"| Classes | {m.get('num_classes',0)} |",
            f"| Funcoes | {m.get('num_functions',0)} |",
            f"| Imports unicos | {m.get('num_imports',0)} |",
            f"| Complexidade media | {m.get('avg_cyclomatic_complexity',0)} |",
            f"| Complexidade maxima | {m.get('max_cyclomatic_complexity',0)} |",
            f"| Maintainability Index | {m.get('maintainability_index',0)} ({m.get('maintainability_grade','N/A')}) |",
        ]
        return "\n".join(lines)

    def _section_criteria(self) -> str:
        criteria = self.analysis.get("criteria", {})
        lines = ["\n## Analise por Criterio\n"]
        for key, value in criteria.items():
            score = value.get("score", 0)
            findings = value.get("findings", [])
            lines += [
                f"### {key}",
                f"**Score:** {score}/10 {self._score_bar(score)} | **Status:** {value.get('status','N/A')} | **Severidade:** {value.get('severity','MEDIA')}",
            ]
            if value.get("description") and not self.compact:
                lines.append(f"*{value['description']}*")
            lines.append("")
            if findings:
                lines.append(f"**{len(findings)} problema(s) encontrado(s):**\n")
                for i, f in enumerate(findings, 1):
                    lines.append(f"**{i}. [{f.get('location','')}]** {f.get('issue','')}")
                    sug = f.get("suggestion", "")
                    if self.compact:
                        if sug:
                            lines.append(f"  *Sugestão: {sug}*\n")
                    else:
                        meta = self._finding_meta(f, score)
                        lines.append(f"- Impacto estimado: {meta['impact']}")
                        lines.append(f"- Confiança: {meta['confidence']}")
                        content = f.get("line_content", "")
                        if content:
                            lines.append(f"\n```python\n# Codigo atual ({f.get('location','')}):\n{content}\n```")
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
        lines = [
            "\n## Analise de Dependencias\n",
            f"- **Total de imports:** {deps.get('total_imports',0)}",
            f"- **Modulos unicos:** {deps.get('unique_modules',0)}",
        ]
        third = deps.get("third_party", [])
        if third:
            lines.append(f"- **Dependencias externas:** `{'`, `'.join(third)}`")
        duplicates = deps.get("duplicate_imports", [])
        if duplicates:
            lines.append("\n**Imports duplicados encontrados:**\n")
            for d in duplicates:
                lines.append(f"- Linha {d['lineno']}: `{d['module']}` - {d['issue']}")
        circular = deps.get("circular_dependencies", [])
        if circular:
            lines.append("\n**Dependencias circulares encontradas:**\n")
            for cycle in circular[:MAX_CYCLES_LISTED]:
                if isinstance(cycle, list):
                    lines.append(f"- `{' -> '.join(cycle)}`")
        inline = deps.get("inline_imports", [])
        if inline:
            lines.append("\n**Imports dentro de funcoes (anti-pattern):**\n")
            for imp in inline:
                lines.append(
                    f"- Linha {imp['lineno']}: `import {imp['module']}` "
                    f"dentro de `{imp['inside_function']}()`"
                )
        coupling = deps.get("coupling_score", {})
        if coupling.get("issues"):
            lines.append("\n**Problemas de acoplamento:**\n")
            for issue in coupling["issues"]:
                lines.append(f"- {issue}")
        return "\n".join(lines)

    def _section_tools(self) -> str:
        tf = self.analysis.get("tool_findings", {})
        warnings = self.analysis.get("tool_warnings", [])
        lines = ["\n## Ferramentas Externas\n"]

        if warnings:
            for w in warnings:
                lines.append("> [!WARNING]")
                lines.append(f"> **Analise Parcial:** {w}.")
                lines.append("> Execute `code-analyze setup` para instalar dependencias de analise externa.\n")

        has_findings = False
        for tool in ["ruff"]:
            findings = tf.get(tool, [])
            if findings:
                has_findings = True
                lines.append(f"### {tool.capitalize()} ({len(findings)} ocorrencias)\n")
                for f in findings[:MAX_FINDINGS_PER_DETECTOR]:
                    lines.append(f"- **Linha {f.get('lineno','?')}** [{f.get('code','')}]: {f.get('issue','')}")
                lines.append("")

        if not has_findings and not warnings:
            lines.append("Ruff nao encontrado ou sem problemas.\n")

        return "\n".join(lines)

    def _section_tests(self) -> str:
        tests = self.analysis.get("test_analysis", {})
        if not tests:
            return ""
        lines = [
            "\n## Analise de Testes\n",
            "| Item | Valor |", "|------|-------|",
            f"| Funcoes de teste | {tests.get('test_functions',0)} |",
            f"| Classes de teste | {tests.get('test_classes',0)} |",
            f"| Usa pytest | {'Sim' if tests.get('uses_pytest') else 'Nao'} |",
            f"| Cobertura estimada | {tests.get('estimated_coverage',0)}% |",
        ]
        missing = tests.get("missing_tests", [])
        if missing:
            lines.append(f"\n**Metodos sem testes ({len(missing)}):**\n")
            for m in missing:
                lines.append(f"- `{m}`")
        return "\n".join(lines)

    def _section_test_pain(self) -> str:
        """v5.0.0: Test Pain metrics section."""
        tp = self.analysis.get("test_pain", {})
        if not tp:
            return ""
        aggregate = tp.get("aggregate", 0)
        label = "Baixa" if aggregate >= 70 else "Media" if aggregate >= 40 else "Alta"
        lines = [
            "\n## Dor de Teste (v5.0.0)\n",
            f"**Score agregado:** {aggregate}/100 ({label})",
            f"Arquivo de teste: `{tp.get('test_file', 'nao encontrado')}`",
            "",
            "| Métrica | Score | Detalhes |",
            "|---------|-------|----------|",
        ]
        tp1 = tp.get("tp1", {})
        lines.append(
            f"| Cobertura real | {tp1.get('score', 0)}/100 | "
            f"{tp1.get('covered', 0)}/{tp1.get('total', 0)} funções cobertas |"
        )
        tp2 = tp.get("tp2", {})
        lines.append(
            f"| Mock density | {tp2.get('score', 0)}/100 | "
            f"{tp2.get('mock_count', 0)} mocks em {tp2.get('test_funcs', 0)} funções "
            f"(densidade: {tp2.get('density', 0)}) |"
        )
        tp3 = tp.get("tp3", {})
        lines.append(
            f"| Complexidade dos testes | {tp3.get('score', 0)}/100 | "
            f"média {tp3.get('avg_complexity', 0)} em {tp3.get('test_funcs', 0)} funções |"
        )
        tp4 = tp.get("tp4", {})
        deps = tp4.get("external_deps", [])
        deps_str = ", ".join(deps) if deps else "nenhuma"
        lines.append(
            f"| Isolamento | {tp4.get('score', 0)}/100 | "
            f"dependências externas: {deps_str} |"
        )
        lines.append("")
        lines.append(f"_Mock density alta (>0.3) revela acoplamento real não visível no AST._")
        lines.append(f"_Dependências de DB/network nos testes indicam acoplamento a infraestrutura._")
        return "\n".join(lines)

    def _section_recommendations(self) -> str:
        recs = self._generate_recommendations()
        if not recs:
            return "\n## Recomendacoes\n\nNenhum problema critico encontrado.\n"
        lines = ["\n## Recomendacoes Priorizadas\n"]
        for i, rec in enumerate(recs, 1):
            lines.append(f"### {i}. [{rec.get('priority','MEDIA')}] {rec.get('title','')}")
            lines.append(rec.get("description", ""))
            action = rec.get("action", "")
            if action:
                lines.append(f"\n**Acao:** {action}\n")
            else:
                lines.append("")
        return "\n".join(lines)

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

    def save_reports(self, output_dir: Optional[str] = None, generate_html: bool = False) -> Dict[str, str]:
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
        except Exception as exc:
            log_path = self.artifacts.path_for("log", "report_generation_error.log")
            log_payload = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            try:
                self._write_text_atomic(log_path, log_payload)
                self.artifacts.record("log", log_path, status="error", description="Falha ao gerar relatorios", metadata={"error": str(exc)})
            except Exception:
                _log.error("Failed to write error log for report generation", exc_info=True)
            return {"error": f"Erro ao gerar relatorios: {exc}", "log_file": str(log_path)}


def generate_reports(
    filepath: str,
    analysis: Dict[str, Any],
    output_dir: Optional[str] = None,
    artifact_registry: Optional[ArtifactRegistry] = None,
    generate_html: bool = False,
) -> Dict[str, str]:
    try:
        generator = ReportGenerator(filepath, analysis, artifact_registry=artifact_registry, output_dir=output_dir)
        return generator.save_reports(None if artifact_registry else output_dir, generate_html=generate_html)
    except Exception as exc:
        return {"error": f"Erro ao gerar relatorios: {exc}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python report_generator.py <arquivo.py>")
        sys.exit(1)
    dummy: Dict[str, Any] = {
        "metrics": {"lines_of_code": 100, "code_lines": 80, "comment_lines": 10, "blank_lines": 10,
                    "num_classes": 2, "num_functions": 5, "num_imports": 3,
                    "avg_cyclomatic_complexity": 2.0, "max_cyclomatic_complexity": 5,
                    "maintainability_index": 72.0, "maintainability_grade": "B (Good)", "comment_ratio": 12.5},
        "criteria": {},
    }
    result = generate_reports(sys.argv[1], dummy)
    print(json.dumps(result, indent=2, ensure_ascii=False))
