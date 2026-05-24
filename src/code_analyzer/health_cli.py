"""IL9 — `code-analyze health` detector health report.

Reads .analyzer_intent.json and shows per-criterion answer statistics:
  ruidoso      — ≥10 answers, ≥70% non-bug  → informational mode active (IL8)
  saudável     — ≥10 answers, ≥70% bug      → detector working well for this project
  misto        — ≥10 answers, no clear majority
  insuficiente — <10 answers, not enough data
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

_C_RESET  = "\033[0m"
_C_BOLD   = "\033[1m"
_C_YELLOW = "\033[93m"
_C_GREEN  = "\033[92m"
_C_CYAN   = "\033[96m"
_C_GRAY   = "\033[90m"

_LABEL_STYLE: Dict[str, str] = {
    "ruidoso":      f"{_C_YELLOW}⚠ ruidoso{_C_RESET}",
    "saudável":     f"{_C_GREEN}✓ saudavel{_C_RESET}",
    "misto":        f"{_C_CYAN}~ misto{_C_RESET}",
    "insuficiente": f"{_C_GRAY}· insuficiente (< 10){_C_RESET}",
}

_HELP = """\
Uso: code-analyze health

Exibe estatísticas de saúde dos detectores com base nas decisões
registradas em .analyzer_intent.json do projeto atual.

Sem subcomandos — apenas rode: code-analyze health
"""


def _resolve_store():
    from code_analyzer.intent_store import IntentStore
    from code_analyzer.project_context import _find_project_root
    root = _find_project_root(Path.cwd())
    if root is None:
        print("Erro: nao encontrei a raiz do projeto (git root ou pyproject.toml).")
        sys.exit(1)
    return IntentStore(str(root))


def run_health_cli(argv: List[str]) -> int:
    """Print detector health report for the current project."""
    if argv and argv[0] in ("-h", "--help"):
        print(_HELP)
        return 0

    store = _resolve_store()
    rows = store.criteria_stats()
    total_decisions = sum(r["total"] for r in rows)

    print()
    print(f"  {_C_BOLD}Saude dos Detectores{_C_RESET} — .analyzer_intent.json")

    if not rows:
        print("  Nenhuma decisao registrada.")
        print('  Execute "code-analyze <arquivo>" para iniciar uma sessao de perguntas.')
        return 0

    print(f"  {total_decisions} decisao(oes) registrada(s) · {len(rows)} criterio(s)\n")

    col_crit = max(len(r["criterion"]) for r in rows)
    col_crit = max(col_crit, 20)
    header = f"  {'Criterio':<{col_crit}}  {'Respostas':>9}  {'FP':>5}  {'Bug':>5}  Status"
    sep = "  " + "─" * (col_crit + 32)
    print(header)
    print(sep)

    for r in rows:
        crit = r["criterion"]
        total = r["total"]
        if r["label"] == "insuficiente":
            fp_str = " —"
            bug_str = " —"
        else:
            fp_str = f"{int(r['fp_rate'] * 100):>4}%"
            bug_str = f"{int(r['bug_rate'] * 100):>4}%"
        status = _LABEL_STYLE.get(r["label"], r["label"])
        print(f"  {crit:<{col_crit}}  {total:>9}  {fp_str}  {bug_str}  {status}")

    print()
    counts = {label: sum(1 for r in rows if r["label"] == label)
              for label in ("ruidoso", "saudável", "misto", "insuficiente")}
    parts = []
    if counts["ruidoso"]:
        parts.append(f"{_C_YELLOW}{counts['ruidoso']} ruidoso(s){_C_RESET}")
    if counts["saudável"]:
        parts.append(f"{_C_GREEN}{counts['saudável']} saudavel(is){_C_RESET}")
    if counts["misto"]:
        parts.append(f"{_C_CYAN}{counts['misto']} misto(s){_C_RESET}")
    if counts["insuficiente"]:
        parts.append(f"{_C_GRAY}{counts['insuficiente']} insuficiente(s){_C_RESET}")
    print("  " + " · ".join(parts))

    if counts["insuficiente"]:
        print(f"\n  {_C_GRAY}Critérios insuficientes ganham classificação após ≥10 respostas.{_C_RESET}")

    print()
    return 0
