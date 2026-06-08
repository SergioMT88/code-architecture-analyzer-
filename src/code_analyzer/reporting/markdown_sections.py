from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from code_analyzer.constants import MOCK_DENSITY_THRESHOLD
from code_analyzer.history import load_history
from code_analyzer.limits import (
    MAX_CYCLES_LISTED,
    MAX_FINDINGS_PER_DETECTOR,
    MAX_REPORT_TOP_ITEMS,
)
from code_analyzer.pattern_advisor import get_pattern_advice


class MarkdownSections:

    def __init__(self, parent: Any) -> None:
        self._p = parent

    @staticmethod
    def _score_bar(score: int) -> str:
        filled = round(score / 2)
        return "[" + "#" * filled + "-" * (5 - filled) + "]"

    @staticmethod
    def _finding_meta(finding: Dict[str, Any], score: int) -> Dict[str, str]:
        severity = str(finding.get("severity", "MEDIA")).upper()
        impact_map = {"ALTA": "Alto impacto", "MEDIA": "Impacto moderado", "BAIXA": "Impacto baixo"}
        confidence = "Alta" if score >= 8 else "Média" if score >= 6 else "Baixa"
        return {"impact": impact_map.get(severity, "Impacto moderado"), "confidence": confidence}

    @staticmethod
    def _inline_text(value: Any, limit: int = 90) -> str:
        text = str(value).replace("|", "\\|").replace("\n", " ").strip()
        return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."

    def section_priority_index(self) -> str:
        pi = self._p.analysis.get("priority_index")
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
            "| Fator | Valor |",
            "|-------|-------|",
            f"| Fan-in (arquivos que importam este modulo) | {fan_in} |",
            f"| Commits recentes (90 dias) | {commits} |",
            f"| Cobertura de testes estimada | {coverage}% |",
            f"\n*{pi.get('reason', '')}*\n",
        ]
        return "\n".join(lines)

    def section_pattern_advisor(self) -> str:
        advice = get_pattern_advice(self._p.analysis)
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

    def section_equivalence(self) -> str:
        purity_map = self._p.analysis.get("purity_map", {})
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

    def section_project_context(self) -> str:
        ctx = self._p.analysis.get("project_context", {})
        if not ctx.get("found"):
            return ""
        lines = ["\n## Contexto do Projeto (CLAUDE.md)\n"]
        if ctx.get("file_mentioned"):
            lines.append(f"> **Este arquivo é mencionado no CLAUDE.md** — verifique se há débitos ou bugs conhecidos relativos a `{self._p.filepath.name}`.\n")
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

    def section_summary(self) -> str:
        summary = self._p._generate_summary()
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

    def section_action_plan(self) -> str:
        recs = self._p._generate_recommendations()
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

    def section_metrics(self) -> str:
        m = self._p.analysis.get("metrics", {})
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

    def section_criteria(self) -> str:
        criteria = self._p.analysis.get("criteria", {})
        lines = ["\n## Analise por Criterio\n"]
        for key, value in criteria.items():
            score = value.get("score", 0)
            findings = value.get("findings", [])
            lines += [
                f"### {key}",
                f"**Score:** {score}/10 {self._score_bar(score)} | **Status:** {value.get('status','N/A')} | **Severidade:** {value.get('severity','MEDIA')}",
            ]
            if value.get("description") and not self._p.compact:
                lines.append(f"*{value['description']}*")
            lines.append("")
            if findings:
                lines.append(f"**{len(findings)} problema(s) encontrado(s):**\n")
                for i, f in enumerate(findings, 1):
                    lines.append(f"**{i}. [{f.get('location','')}]** {f.get('issue','')}")
                    sug = f.get("suggestion", "")
                    if self._p.compact:
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

    def section_dependencies(self) -> str:
        deps = self._p.analysis.get("dependencies", {})
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

    def section_tools(self) -> str:
        tf = self._p.analysis.get("tool_findings", {})
        warnings = self._p.analysis.get("tool_warnings", [])
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

    def section_tests(self) -> str:
        tests = self._p.analysis.get("test_analysis", {})
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

    def section_test_pain(self) -> str:
        tp = self._p.analysis.get("test_pain", {})
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
        lines.append(f"_Mock density alta (>{MOCK_DENSITY_THRESHOLD}) revela acoplamento real não visível no AST._")
        lines.append("_Dependências de DB/network nos testes indicam acoplamento a infraestrutura._")
        return "\n".join(lines)

    def section_test_practices(self) -> str:
        tp = self._p.analysis.get("test_practices", {})
        if not tp:
            return ""
        overall = tp.get("overall_score", 0)
        label = "Otimo" if overall >= 80 else "Bom" if overall >= 60 else "Regular" if overall >= 40 else "Fraco"

        lines = [
            "\n## Praticas de Teste (v7.1.0)\n",
            f"**Score geral:** {overall}/100 ({label})",
            "",
            "| Dimensao | Score | Detalhes |",
            "|----------|-------|----------|",
        ]

        tp1 = tp.get("test_passing", {})
        status_map = {"pass": "Aprovado", "fail": "Falhou", "no_tests": "Sem testes", "error": "Erro"}
        status = status_map.get(tp1.get("status", ""), "N/A")
        tp1_detail = f"{tp1.get('passed', 0)} pass, {tp1.get('failed', 0)} fail"
        if tp1.get("test_file"):
            tp1_detail += f" ({Path(tp1['test_file']).name})"
        lines.append(f"| 1. Testes aprovados | {tp1.get('score', 0)}/100 | {status} — {tp1_detail} |")

        tc = tp.get("test_coverage", {})
        tc_detail = f"{tc.get('coverage_pct', 0)}% funcoes testadas"
        untested = tc.get("untested_functions", [])
        if untested:
            tc_detail += f" (sem teste: {', '.join(untested[:3])}{'...' if len(untested) > 3 else ''})"
        lines.append(f"| 2. Cobertura de funcoes | {tc.get('score', 0)}/100 | {tc_detail} |")

        ec = tp.get("edge_cases", {})
        patterns = ec.get("patterns_found", {})
        ec_detail = f"{ec.get('total_patterns', 0)} padroes"
        if patterns:
            ec_detail += f" ({', '.join(patterns.keys())})"
        lines.append(f"| 3. Casos extremos | {ec.get('edge_case_score', 0)}/100 | {ec_detail} |")

        tt = tp.get("test_type", {})
        balance_map = {"good": "Balanceado", "skewed_unit": "Apenas unit", "skewed_integration": "Apenas integ", "no_tests": "Sem testes"}
        balance = balance_map.get(tt.get("balance", ""), "N/A")
        lines.append(f"| 4. Unit vs Integracao | {tt.get('score', 0)}/100 | {balance} |")

        nfr = tp.get("nfr_tests", {})
        nfr_types = nfr.get("nfr_types_found", [])
        nfr_detail = ", ".join(nfr_types) if nfr_types else "Nenhum NFR testado"
        lines.append(f"| 5. NFRs (performance etc.) | {nfr.get('score', 0)}/100 | {nfr_detail} |")

        return "\n".join(lines)

    def section_recommendations(self) -> str:
        recs = self._p._generate_recommendations()
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

    def section_history(self) -> str:
        snapshots = load_history(str(self._p.filepath))
        if not snapshots:
            return ""
        lines = [
            "\n## Historico de Evolucao\n",
            "| Execucao | MI | Grade | Criterios com problemas |",
            "|---|---|---|---|",
        ]
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
