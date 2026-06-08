from __future__ import annotations

import html as _html
from typing import Any, Dict, List

from code_analyzer._version import __version__
from code_analyzer.history import load_history
from code_analyzer.limits import MAX_REPORT_TOP_ITEMS


class HtmlSections:

    GRADE_COLORS = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}

    def __init__(self, parent: Any) -> None:
        self._p = parent

    @staticmethod
    def _html_esc(t: Any) -> str:
        return _html.escape(str(t))

    @staticmethod
    def _html_score_bar(score: int) -> str:
        w = max(0, min(100, score * 10))
        color = "#22c55e" if score >= 7 else ("#f59e0b" if score >= 5 else "#ef4444")
        return f'<div class="sb"><div class="sb-f" style="width:{w}%;background:{color}"></div></div>'

    def _html_cards(self, items: list, title: str) -> str:
        if not items:
            return ""
        esc = self._html_esc
        parts = []
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
            parts.append(
                f'<div class="card card-{cls}">'
                f'<div class="card-h"><span class="card-t">{esc(name)}</span>'
                f'<span class="card-sc">{s}/10</span></div>'
                f"{self._html_score_bar(s)}"
                f'<div class="card-sev">{esc(val.get("description",""))}</div>'
                + (f'<div class="card-n">{len(findings)} problema(s)</div>' if findings else '<div class="card-n ok">✓ Sem problemas</div>')
                + details
                + "</div>"
            )
        rows = "".join(parts)
        return f"<h2>{esc(title)}</h2><div class=\"grid\">{rows}</div>" if rows else ""

    def _html_history(self) -> str:
        esc = self._html_esc
        snapshots = load_history(str(self._p.filepath))
        if not snapshots:
            return ""
        row_parts = []
        for s in snapshots[-5:]:
            ts = esc(s.get("timestamp", "")[:19].replace("T", " "))
            mi = int(s.get("maintainability_index", 100.0))
            grade = esc(s.get("maintainability_grade", "A"))
            problems = []
            for k, v in s.get("scores", {}).items():
                if v < 10.0:
                    problems.append(f"{esc(k)} ({v:.1f})")
            problems_str = ", ".join(problems) if problems else "Nenhum"
            row_parts.append(
                f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>{ts}</td>"
                f"<td style='padding: 8px; border: 1px solid #ddd;'>{mi}</td>"
                f"<td style='padding: 8px; border: 1px solid #ddd;'>{grade}</td>"
                f"<td style='padding: 8px; border: 1px solid #ddd;'>{problems_str}</td></tr>"
            )
        rows = "".join(row_parts)
        return f'''
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
            <tbody>{rows}</tbody>
        </table>'''

    def _html_recommendations(self, recs: list) -> str:
        esc = self._html_esc
        parts = []
        for i, r in enumerate(recs[:MAX_REPORT_TOP_ITEMS], 1):
            p = esc(r.get("priority", "MEDIA"))
            t = esc(r.get("title", ""))
            d = esc(r.get("description", ""))
            a = esc(r.get("action", ""))
            pc = "al" if p == "ALTA" else "me" if p == "MEDIA" else "ba"
            parts.append(
                f'<div class="rec {pc}"><span class="rec-badge {pc}">{p}</span>'
                f"<strong>{t}</strong><p>{d}</p>"
                + (f'<div class="rec-a">➜ {a}</div>' if a else "")
                + "</div>"
            )
        block = "".join(parts)
        return f'<h2>🎯 Recomendacoes</h2>{block}' if block else ""

    def _html_deps(self, deps: dict) -> str:
        esc = self._html_esc
        parts = []
        if deps:
            tpi = deps.get("third_party", [])
            crc = deps.get("circular_dependencies", [])
            dup = deps.get("duplicate_imports", [])
            parts.append(f'<div class="m-card"><strong>Imports:</strong> {deps.get("total_imports",0)} total, {deps.get("unique_modules",0)} unicos</div>')
            if tpi:
                parts.append(f'<div class="m-card"><strong>Externos:</strong> {" ".join(esc(x) for x in tpi)}</div>')
            for c in crc[:MAX_REPORT_TOP_ITEMS]:
                pth = " -> ".join(c) if isinstance(c, list) else str(c)
                parts.append(f'<div class="m-card crit"><strong>Circular:</strong> {esc(pth)}</div>')
            for d in dup[:MAX_REPORT_TOP_ITEMS]:
                parts.append(f'<div class="m-card warn"><strong>Duplicado:</strong> {esc(d.get("module",""))} (linha {d.get("lineno","?")})</div>')
        return "".join(parts) if parts else '<div class="m-card">Nenhuma dependencia analisada.</div>'

    def _html_tests(self, tests: dict) -> str:
        esc = self._html_esc
        if not tests:
            return '<div class="m-card">Nenhuma analise de testes disponivel.</div>'
        cov = tests.get("estimated_coverage", 0)
        cov_color = "#22c55e" if cov >= 50 else "#f59e0b" if cov >= 20 else "#ef4444"
        missing = tests.get("missing_tests", [])
        parts = [
            f'<div class="m-card"><strong>Testes:</strong> {tests.get("test_functions",0)} funcoes, {tests.get("test_classes",0)} classes</div>',
            f'<div class="m-card"><strong>Cobertura estimada:</strong> <span style="color:{cov_color};font-weight:bold">{cov}%</span></div>',
            f'<div class="m-card"><strong>pytest:</strong> {"Sim" if tests.get("uses_pytest") else "Nao"}</div>',
        ]
        if missing:
            parts.append(
                f'<div class="m-card warn"><strong>Sem teste ({len(missing)}):</strong> '
                f'{" ".join(esc(m) for m in missing[:MAX_REPORT_TOP_ITEMS])}</div>'
            )
        return "".join(parts)

    def _html_tools(self) -> str:
        esc = self._html_esc
        parts = []
        tf = self._p.analysis.get("tool_findings", {})
        if tf.get("total", 0):
            for tn in ["ruff"]:
                fts = tf.get(tn, [])
                if fts:
                    items_html = "".join(
                        f'<li><code>{esc(f.get("code",""))}</code> — {esc(f.get("issue",""))[:80]}</li>'
                        for f in fts[:8]
                    )
                    parts.append(f'<div class="m-card"><strong>{tn}:</strong> {len(fts)} ocorrencias<ul>{items_html}</ul></div>')
        for w in self._p.analysis.get("tool_warnings", []):
            parts.append(
                f'<div class="m-card warn" style="border-left:4px solid #ef4444;background:#fef2f2;color:#991b1b;margin-bottom:10px">'
                f'<strong>⚠ Analise Parcial:</strong> {esc(w)}.<br>'
                f'Execute <code>code-analyze setup</code> no terminal para instalar ferramentas ausentes.</div>'
            )
        return "".join(parts)

    @staticmethod
    def _html_score_disclaimer() -> str:
        return (
            '<div style="background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #f59e0b;'
            'border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:.82rem;color:#78350f;">'
            '<strong>Escopo do score:</strong> mede convenções estruturais e anti-patterns detectáveis '
            'estaticamente (SOLID, complexidade, acoplamento). '
            'Bugs semânticos — lógica de negócio incorreta, comportamento inesperado de ORM, '
            'race conditions — <strong>não são detectados automaticamente</strong>. '
            'Um score alto não garante ausência de bugs funcionais.</div>'
        )

    def _html_project_context(self) -> str:
        esc = self._html_esc
        pctx = self._p.analysis.get("project_context", {})
        if not pctx.get("found"):
            return ""
        debt_items = "".join(f"<li>{esc(d)}</li>" for d in pctx.get("known_debts", []))
        mention_badge = (
            f'<div style="background:#fef2f2;color:#991b1b;padding:6px 10px;'
            f'border-radius:6px;margin-bottom:8px;font-size:.82rem;">'
            f'<strong>⚠ Este arquivo é mencionado no CLAUDE.md</strong> — '
            f'verifique se há débitos ou bugs conhecidos relativos a <code>{esc(self._p.filepath.name)}</code>.</div>'
        ) if pctx.get("file_mentioned") else ""
        debt_block = (
            f'<strong>Indicadores de débito técnico no CLAUDE.md:</strong>'
            f'<ul style="margin:6px 0 0 16px;font-size:.82rem;color:#475569;">{debt_items}</ul>'
        ) if debt_items else ""
        return (
            f'<h2>📋 Contexto do Projeto (CLAUDE.md)</h2>'
            f'<div class="m-card" style="margin-bottom:16px;">'
            f'{mention_badge}{debt_block}'
            f'<div style="font-size:.75rem;color:#94a3b8;margin-top:6px;">Fonte: {esc(pctx.get("path","CLAUDE.md"))}</div>'
            f'</div>'
        )

    @staticmethod
    def _html_css(grade_color: str) -> str:
        return f'''<style>
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
</style>'''

    def generate_html_report(self) -> str:
        summary = self._p._generate_summary()
        metrics = self._p.analysis.get("metrics", {})
        criteria = self._p.analysis.get("criteria", {})
        recs = self._p._generate_recommendations()
        esc = self._html_esc

        grade_color = self.GRADE_COLORS.get(summary["grade"], "#6b7280")
        grouped: Dict[str, List] = {"ALTA": [], "MEDIA": [], "BAIXA": []}
        for k, v in criteria.items():
            findings = v.get("findings", [])
            if not findings:
                continue
            sev = v.get("severity", "MEDIA").upper()
            if sev in grouped:
                grouped[sev].append((k, v))

        criteria_keys_ok = [k for k, v in criteria.items() if v.get("score", 10) >= 7]
        criteria_keys_warn = [k for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]
        criteria_keys_crit = [k for k, v in criteria.items() if v.get("score", 10) < 5]

        overall = summary["overall_score"]
        raw = summary.get("raw_score", overall)
        security_penalty = summary.get("security_penalty", 0)

        risk = summary.get("production_risk", {})
        risk_score = risk.get("score", 0)
        risk_label = risk.get("label", "N/A")
        risk_cls = "crit" if risk_score >= 70 else "warn" if risk_score >= 40 else "ok"

        tool_block = self._html_tools()
        penalty_note = ""
        if security_penalty > 0:
            penalty_note = f"""<div style="background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #ef4444;border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:.82rem;color:#991b1b;"><strong>Score penalizado:</strong> {esc(str(raw))}/10 → <strong>{overall}/10</strong> (-{esc(str(security_penalty))} por seguranca: secrets, injection, mass assignment detectados)</div>"""

        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analyzer - {esc(self._p.filepath.name)}</title>
{self._html_css(grade_color)}</head>
<body><div class="container">
<div class="hero">
<h1>📊 {esc(self._p.filepath.name)}</h1>
<div class="score">{overall}</div>
<div class="grade">{summary["grade"]}</div>
<div class="meta">{esc(str(self._p.filepath))} &middot; {esc(self._p.timestamp[:10])}</div>
<div class="badges">
<span class="badge crit">🔴 {len(criteria_keys_crit)} Criticos</span>
<span class="badge warn">🟡 {len(criteria_keys_warn)} Avisos</span>
<span class="badge ok">🟢 {len(criteria_keys_ok)} OK</span>
<span class="badge">{summary["total_findings"]} achados reais</span>
<span class="badge {risk_cls}">Risco: {risk_score}/100 ({risk_label})</span>
<span class="badge">{metrics.get("maintainability_grade","N/A")}</span>
</div></div>

{self._html_score_disclaimer()}
{penalty_note}
{self._html_project_context()}
{self._html_cards(grouped.get("ALTA",[]),"🔴 Alta Severidade")}
{self._html_cards(grouped.get("MEDIA",[]),"🟡 Media Severidade")}
{self._html_cards(grouped.get("BAIXA",[]),"🔵 Baixa Severidade")}

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
<div class="metrics">{self._html_deps(self._p.analysis.get("dependencies", {}))}</div>

<h2>🧪 Testes</h2>
<div class="metrics">{self._html_tests(self._p.analysis.get("test_analysis", {}))}</div>

{f'<h2>🔧 Ferramentas Externas</h2><div class="metrics">{tool_block}</div>' if tool_block else ''}

{self._html_recommendations(recs)}

{self._html_history()}

<div class="footer">Code Architecture Analyzer v{__version__} &middot; {esc(self._p.timestamp)}</div>
</div></body></html>'''
