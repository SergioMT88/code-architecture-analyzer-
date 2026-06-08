"""Terminal UI helpers — pure presentation layer with no business logic."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from code_analyzer.constants import CRITERIA_WEIGHT, MI_WEIGHT

_log = logging.getLogger(__name__)


@dataclass
class ScoreBundle:
    """Pre-computed scoring values shared across UI and gate functions."""
    criteria_avg: float
    avg_score: float
    grade: str
    critical: List[tuple]
    warnings: List[tuple]
    total_findings: int
    mi: float
    mg: str
    risk_score: float
    risk_label: str
    test_pain_aggregate: float


def _compute_score_bundle(analysis: Dict[str, Any]) -> ScoreBundle:
    """Compute derived scores once — shared across print functions and min-score gate."""
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})
    scores = [v.get("score", 0) for v in criteria.values()]
    criteria_avg = round(sum(scores) / max(1, len(scores)), 1)
    mi = metrics.get("maintainability_index", 0)
    mi_component = min(10.0, mi / 10.0)
    avg_score = round(criteria_avg * CRITERIA_WEIGHT + mi_component * MI_WEIGHT, 1)
    grade = "A" if avg_score >= 9 else "B" if avg_score >= 7 else "C" if avg_score >= 5 else "D"
    risk = analysis.get("production_risk", {})
    return ScoreBundle(
        criteria_avg=criteria_avg,
        avg_score=avg_score,
        grade=grade,
        critical=[(k, v) for k, v in criteria.items() if v.get("score", 10) < 5],
        warnings=[(k, v) for k, v in criteria.items() if 5 <= v.get("score", 10) < 7],
        total_findings=sum(len(v.get("findings", [])) for v in criteria.values()),
        mi=mi,
        mg=metrics.get("maintainability_grade", "N/A"),
        risk_score=risk.get("score", 0),
        risk_label=risk.get("label", "Desconhecido"),
        test_pain_aggregate=analysis.get("test_pain", {}).get("aggregate", 0.0),
    )


def score_bar(n: int, total: int = 10, size: int = 10) -> str:
    filled = round(n / max(total, 1) * size)
    fg = 92 if n >= 7 else 93 if n >= 5 else 91
    return f"\033[{fg}m" + "#" * filled + "\033[90m" + "-" * (size - filled) + "\033[0m"


def grade_color(grade: str) -> str:
    return {"A": "\033[92m", "B": "\033[94m", "C": "\033[93m", "D": "\033[91m"}.get(grade, "\033[0m")


def print_phase(phase: str, subtitle: str = "", quiet: bool = False, json_mode: bool = False) -> None:
    if json_mode:
        return
    if quiet:
        print(f"\n[{phase}]")
        if subtitle:
            print(f"  {subtitle}")
        return
    print(f"\n{'='*70}")
    print(f"  {phase}")
    if subtitle:
        print(f"  {subtitle}")
    print("=" * 70)


def print_executive_summary(
    filepath: str,
    analysis: Dict[str, Any],
    artifact_registry: Any = None,
    json_mode: bool = False,
) -> ScoreBundle:
    if json_mode:
        return _compute_score_bundle(analysis)
    sb = _compute_score_bundle(analysis)
    bar = score_bar(sb.avg_score)
    gc = grade_color(sb.grade)
    print(f"\n  \033[1m{bar}  {sb.avg_score}/10  ({gc}{sb.grade}\033[0m\033[1m)\033[0m  \033[90m{Path(filepath).name}\033[0m")
    print(f"  \033[90m{'-'*50}\033[0m")
    rc = "\033[91m" if sb.risk_label == "Critico" else "\033[93m" if sb.risk_label == "Risco" else "\033[92m"
    print(
        f"  \033[90mMI:\033[0m {sb.mi} ({sb.mg})  "
        f"Risco de Producao: {rc}{sb.risk_score}/100 ({sb.risk_label})\033[0m"
    )
    print(
        f"  \033[91m! {len(sb.critical)} critico(s)\033[0m  "
        f"\033[93m* {len(sb.warnings)} aviso(s)\033[0m  "
        f"\033[94m. {sb.total_findings} finding(s)\033[0m"
    )
    return sb


def print_project_context(analysis: Dict[str, Any], filepath: str) -> None:
    ctx = analysis.get("project_context", {})
    if not ctx.get("found"):
        return
    print(f"\n  \033[1m\033[94m[CLAUDE.md]\033[0m Contexto do projeto carregado: {ctx.get('path', '')}")
    if ctx.get("file_mentioned"):
        print(f"  \033[93m! '{Path(filepath).name}' e mencionado no CLAUDE.md - verifique debitos conhecidos.\033[0m")
    debts = ctx.get("known_debts", [])
    if debts:
        print(f"  \033[90mIndicadores de debito tecnico ({len(debts)} linhas):\033[0m")
        for d in debts[:5]:
            safe = d[:120].encode("cp1252", errors="replace").decode("cp1252")
            print(f"    \033[90m- {safe}\033[0m")
        if len(debts) > 5:
            print(f"    \033[90m... +{len(debts) - 5} linha(s) adicionais no CLAUDE.md\033[0m")


def print_priority_index(analysis: Dict[str, Any]) -> None:
    pi = analysis.get("priority_index")
    if not pi:
        return
    fan_in = pi.get("fan_in", 0)
    commits = pi.get("commit_count", 0)
    coverage = pi.get("coverage_pct", 0)
    label = pi.get("label", "")
    score = pi.get("score", 0)
    lc = "\033[91m" if label == "CRITICO" else "\033[93m" if label == "ALTA" else "\033[94m"
    print(f"\n  \033[1m[Prioridade Contextual]\033[0m {lc}{label}\033[0m ({score}/100)")
    print(f"    fan-in: {fan_in} arquivo(s) importam este modulo")
    print(f"    commits (90d): {commits}  |  cobertura estimada: {coverage}%")
    print(f"    \033[90m{pi.get('reason', '')}\033[0m")


def print_equivalence_confidence(analysis: Dict[str, Any]) -> None:
    purity_map = analysis.get("purity_map", {})
    if not purity_map:
        return
    total = sum(len(v) for v in purity_map.values())
    print(f"\n  \033[1m\033[96m[Equivalencia de Extracao]\033[0m {total} candidato(s) classificado(s):")
    for func_name, candidates in purity_map.items():
        for c in candidates:
            purity = c.get("purity", "unknown")
            if purity == "pure":
                badge = "\033[92mAlta\033[0m   (pura)"
            elif purity == "side_effect":
                badge = "\033[93mMedia\033[0m  (side_effect)"
            else:
                badge = "\033[91mBaixa\033[0m  (desconhecida)"
            reasons = c.get("reasons", [])
            reason_str = f" -- {reasons[0]}" if reasons else ""
            print(
                f"    \033[1m{func_name}\033[0m  linhas {c['start_line']}-{c['end_line']}"
                f"  ->  Confianca: {badge}{reason_str}"
            )


def print_pattern_advice(advice: List[Dict[str, str]]) -> None:
    if not advice:
        return
    print(f"\n  \033[1m\033[95m[Padroes de Projeto]\033[0m {len(advice)} sugestao(oes) de refatoracao arquitetural:")
    for item in advice:
        pc = "\033[91m" if item["priority"] == "ALTA" else "\033[93m"
        print(f"    {pc}[{item['priority']}]\033[0m \033[1m{item['pattern']}\033[0m — {item['symptom']}")
        print(f"      \033[90m{item['suggestion']}\033[0m")


def print_noisy_notice(criteria: Dict[str, Any]) -> None:
    """IL8 — Print a notice for criteria auto-detected as noisy by local intent history."""
    noisy = [(name, v) for name, v in criteria.items() if v.get("noisy")]
    if not noisy:
        return
    print(f"\n  \033[1m\033[94m[Aprendizado]\033[0m {len(noisy)} detector(es) em modo informacional neste projeto:")
    for name, v in noisy:
        rate = int(v.get("noisy_fp_rate", 0) * 100)
        print(f"    \033[90m•\033[0m {name} — {rate}% intencional → sem penalidade de score")


def print_findings_summary(analysis: Dict[str, Any], quiet: bool = False, json_mode: bool = False) -> None:
    if json_mode:
        return
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})

    print(
        f"\n  Maintainability Index: "
        f"{metrics.get('maintainability_index', 0)} "
        f"({metrics.get('maintainability_grade', 'N/A')})"
    )
    risk = analysis.get("production_risk", {})
    if risk:
        print(f"  Risco de Producao: {risk.get('score', 0)}/100 ({risk.get('label', 'N/A')})")
    print(f"  Complexidade media: {metrics.get('avg_cyclomatic_complexity', 0)}")
    print(f"  Ratio de comentarios: {metrics.get('comment_ratio', 0)}%\n")

    critical = [(k, v) for k, v in criteria.items() if v.get("score", 10) < 5]
    warnings_list = [(k, v) for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]

    if quiet:
        print(f"  Criticos: {len(critical)} | Avisos: {len(warnings_list)}")
        return

    if critical:
        print(f"\n  \033[1m\033[91m! CRITICO ({len(critical)} criterios):\033[0m")
        for key, val in critical:
            s = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    {score_bar(s)} \033[91m{key}\033[0m ({n} problemas)")
            for finding in val.get("findings", [])[:2]:
                loc = finding.get("location", "")
                iss = finding.get("issue", "")[:80]
                print(f"      \033[90m[{loc}]\033[0m {iss}")

    if warnings_list:
        print(f"\n  \033[1m\033[93m* AVISO ({len(warnings_list)} criterios):\033[0m")
        for key, val in warnings_list:
            s = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    {score_bar(s)} \033[93m{key}\033[0m ({n} problemas)")

    ok_count = sum(1 for v in criteria.values() if v.get("score", 10) >= 7)
    if ok_count:
        print(f"  \033[92m. {ok_count} criterios OK\033[0m")

    tool_findings = analysis.get("tool_findings", {})
    total_tools = tool_findings.get("total", 0)
    if total_tools:
        print(
            f"\n  \033[94mFerramentas externas:\033[0m {total_tools} ocorrencias "
            f"(ruff: {len(tool_findings.get('ruff', []))})"
        )
    for w in analysis.get("tool_warnings", []):
        print(f"  \033[93m!\033[0m {w}")
    if not quiet:
        print(
            "\n  \033[90mNota: score mede convencoes estruturais (SOLID, complexidade, acoplamento).\033[0m"
            "\n  \033[90mBugs semanticos (logica de negocio, ORM, etc.) nao sao detectados automaticamente.\033[0m"
        )


# ---------------------------------------------------------------------------
# First-run welcome
# ---------------------------------------------------------------------------

def _first_run_check() -> bool:
    """Return True on the very first run and mark as welcomed."""
    sentinel = Path.home() / ".code-analyzer" / "welcomed"
    if sentinel.exists():
        return False
    try:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.touch()
    except OSError:
        _log.debug("Failed to create welcome sentinel", exc_info=True)
    return True


def print_welcome() -> None:
    from code_analyzer.i18n import t
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {t('welcome_title')}")
    print(sep)
    print()
    print(t("welcome_body"))
    print()
    print(f"  \033[90m{t('welcome_footer')}\033[0m")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# Contextual "O que fazer agora" / "What to do now"
# ---------------------------------------------------------------------------

def print_next_steps(
    analysis: Dict[str, Any],
    sb: "ScoreBundle",
    il_has_data: bool,
) -> None:
    import re
    from code_analyzer.i18n import t

    criteria = analysis.get("criteria", {})
    steps: List[tuple] = []
    sep_line = "  " + "-" * 54

    # Good state shortcut
    if sb.avg_score >= 8.5 and not sb.critical:
        print(f"\n{sep_line}")
        print(f"  \033[1m{t('next_steps_title')}\033[0m")
        print(sep_line)
        print(f"  \033[92m[+]\033[0m \033[1m{t('good_state_title')}\033[0m")
        print(f"      \033[90m{t('good_state_detail')}\033[0m")
        if il_has_data:
            print(f"  \033[96m[i]\033[0m \033[1m{t('il_existing_title')}\033[0m")
            print(f"      \033[90m{t('il_existing_detail')}\033[0m")
        print(sep_line)
        return

    # Step 1: most impactful structural issue
    god_findings = criteria.get("GodClass", {}).get("findings", [])
    if god_findings:
        biggest_lines = 0
        biggest_name = ""
        for f in god_findings:
            m = re.search(r"'(\w+)'.*?(\d+) linhas", f.get("issue", ""))
            if m and int(m.group(2)) > biggest_lines:
                biggest_lines = int(m.group(2))
                biggest_name = m.group(1)
        if not biggest_name:
            m2 = re.search(r"'(\w+)'", god_findings[0].get("issue", ""))
            biggest_name = m2.group(1) if m2 else "classe"
        if biggest_lines:
            title = t("godclass_title", name=biggest_name, lines=biggest_lines)
        else:
            title = t("godclass_title_nolines", name=biggest_name)
        steps.append(("!", "\033[91m", title, t("godclass_detail")))

    if criteria.get("CircularDeps", {}).get("findings"):
        color = "\033[93m" if steps else "\033[91m"
        steps.append(("!", color, t("circular_title"), t("circular_detail")))

    if not steps and criteria.get("Coupling", {}).get("score", 10) < 5:
        steps.append(("!", "\033[93m", t("coupling_title"), t("coupling_detail")))

    if not steps and criteria.get("DeepNesting", {}).get("findings"):
        steps.append(("!", "\033[93m", t("nesting_title"), t("nesting_detail")))

    # Intent Learning hint (always last)
    if not il_has_data:
        steps.append(("i", "\033[96m", t("il_new_title"), t("il_new_detail")))
    else:
        steps.append(("i", "\033[96m", t("il_existing_title"), t("il_existing_detail")))

    steps = steps[:3]
    if not steps:
        return

    print(f"\n{sep_line}")
    print(f"  \033[1m{t('next_steps_title')}\033[0m")
    print(sep_line)
    for icon, color, title, detail in steps:
        print(f"  {color}[{icon}]\033[0m \033[1m{title}\033[0m")
        print(f"      \033[90m{detail}\033[0m")
    print(sep_line)
