"""Interactive menu — step-by-step questionnaire for the developer."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.artifact_manager import ArtifactRegistry
from code_analyzer.limits import MAX_INTERACTIVE_PREVIEW_ITEMS
from code_analyzer.refactorer import refactor_file
from code_analyzer.report_generator import ReportGenerator, generate_reports

_log = logging.getLogger(__name__)


def _ask_choice(prompt: str, options: list, default: Optional[str] = None) -> str:
    labels = "/".join(o.upper() if o == default else o for o in options)
    try:
        answer = input(f"\n{prompt} [{labels}]: ").strip().lower()
        if not answer and default:
            return default
        return answer if answer in options else (default or options[0])
    except (EOFError, KeyboardInterrupt):
        return default or options[0]


def _ask_user(question: str, default: bool = True) -> bool:
    default_str = "S/n" if default else "s/N"
    try:
        answer = input(f"\n{question} [{default_str}]: ").strip().lower()
        if not answer:
            return default
        return answer in ("s", "sim", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return default


def _get_snippet(filepath: str, location: str, context_size: int = 1) -> str:
    try:
        lines = Path(filepath).read_text(encoding="utf-8").split("\n")
        nums = [int(s) for s in location.split() if s.isdigit()]
        if not nums:
            return ""
        lineno = nums[0]
        start = max(0, lineno - 1 - context_size)
        end = min(len(lines), lineno + context_size)
        return "\n".join(f"  {i+1:4d} | {lines[i]}" for i in range(start, end))
    except (OSError, UnicodeDecodeError, ValueError):
        _log.debug("Failed to extract code snippet for %s", filepath, exc_info=True)
        return ""


def _group_changes_by_rule(changes_detail: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_rule: Dict[str, List[Dict[str, Any]]] = {}
    for ch in changes_detail:
        rule = ch.get("type", "unknown")
        by_rule.setdefault(rule, []).append(ch)
    return by_rule


_RULE_LABELS = {
    "docstring": "Adicionar docstring de modulo",
    "duplicate_import": "Remover imports duplicados",
    "unused_import": "Remover imports nao usados",
    "useless_fstring": "Corrigir f-strings sem placeholders",
    "ambiguous_variable": "Renomear variaveis ambiguas (l, I, O)",
}


def _build_preview(changes: List[Dict[str, Any]]) -> str:
    preview_lines = "\n".join(
        f"      {ch.get('description', '')[:80]}"
        for ch in changes[:MAX_INTERACTIVE_PREVIEW_ITEMS]
    )
    if len(changes) > MAX_INTERACTIVE_PREVIEW_ITEMS:
        preview_lines += (
            f"\n      ... +{len(changes) - MAX_INTERACTIVE_PREVIEW_ITEMS} alteracao(oes)"
        )
    return preview_lines


def _ask_rule_choice(rule_label: str, changes_count: int, preview: str) -> str:
    print(f"\n  {rule_label}? ({changes_count} alteracao(oes))")
    print(preview)
    return _ask_choice("  [a]plicar, [p]ular, [v]er diff, [s]air", ["a", "p", "v", "s"], default="a")


def _show_diff(filepath: str, rule: str, rule_label: str, cached_diffs: Dict[str, str],
               artifact_registry: Optional[ArtifactRegistry]) -> str:
    if rule not in cached_diffs:
        diff_result = refactor_file(
            filepath, dry_run=True,
            output_dir=str(artifact_registry.run_root) if artifact_registry else None,
            artifact_registry=artifact_registry, quiet=True,
            generate_tests=False, enabled_rules=[rule],
        )
        cached_diffs[rule] = diff_result.get("diff", "Sem diff disponivel.")
    diff_text = cached_diffs[rule]
    print(f"\n  --- Diff para: {rule_label} ---")
    diff_lines_list = diff_text.split("\n")
    for j in range(0, len(diff_lines_list), 20):
        for dl in diff_lines_list[j:j+20]:
            print(f"  {dl}")
        if j + 20 < len(diff_lines_list):
            input("\n  [Enter] para continuar...")
    return diff_text


def _select_rules(
    filepath: str, by_rule: Dict[str, List[Dict[str, Any]]],
    artifact_registry: Optional[ArtifactRegistry],
) -> tuple:
    selected_rules: List[str] = []
    cached_diffs: Dict[str, str] = {}
    for rule, items in by_rule.items():
        label = _RULE_LABELS.get(rule, rule)
        preview = _build_preview(items)
        while True:
            ans = _ask_rule_choice(label, len(items), preview)
            if ans == "s":
                print("\n  Operacao cancelada. Nenhuma alteracao foi feita no disco.")
                return (None, cached_diffs)
            if ans == "v":
                _show_diff(filepath, rule, label, cached_diffs, artifact_registry)
                continue
            if ans == "a":
                selected_rules.append(rule)
                break
            if ans == "p":
                break
    return (selected_rules, cached_diffs)


def _apply_refactor(
    filepath: str, artifact_registry: Optional[ArtifactRegistry],
    selected_rules: List[str], local_tests: bool,
) -> None:
    print("\n  Aplicando refatoracao real...")
    result = refactor_file(
        filepath, dry_run=False,
        output_dir=str(artifact_registry.run_root) if artifact_registry else None,
        artifact_registry=artifact_registry, quiet=False,
        generate_tests=local_tests, enabled_rules=selected_rules,
    )
    if result.get("error"):
        print(f"\n  Erro ao aplicar: {result['error']}")
    else:
        print("\n  Correcoes aplicadas com sucesso!")


def interactive_menu(
    filepath: str,
    analysis: Dict[str, Any],
    config: Dict[str, Any],
    artifact_registry: Optional[ArtifactRegistry],
    should_save: bool,
    dry_run: bool,
    no_refactor: bool,
    generate_html: bool,
) -> None:
    """Step-by-step interactive questionnaire for the developer."""
    criteria = analysis.get("criteria", {})

    def show_menu() -> str:
        print("\n" + "=" * 50)
        print("  PROXIMOS PASSOS")
        print("=" * 50)
        print("  1) Ver problemas criticos em detalhe")
        print("  2) Ver recomendacoes priorizadas")
        print("  3) Ver metricas do codigo")
        print("  4) Salvar relatorio em arquivo")
        print("  5) Aplicar correcoes automaticas")
        print("  6) Sair")
        return _ask_choice("Escolha uma opcao", ["1", "2", "3", "4", "5", "6"], default="6")

    def show_critical() -> None:
        crit = [(k, v) for k, v in criteria.items() if v.get("score", 10) < 5]
        if not crit:
            print("\n  Nenhum problema critico encontrado!")
            return
        for key, val in crit:
            score = val.get("score", 0)
            findings = val.get("findings", [])
            print(f"\n  \033[91m! {key}\033[0m (\033[1m{score}/10\033[0m) — {len(findings)} problema(s)")
            print(f"  {val.get('description', '')}")
            for i, f in enumerate(findings, 1):
                print(f"\n    {i}. [{f.get('location', '')}] {f.get('issue', '')}")
                sug = f.get("suggestion", "")
                if sug:
                    print(f"       \033[92mSugestao:\033[0m {sug}")
                choice_show = _ask_choice("    Mostrar codigo (s=Sim, c=Contexto ampliado, n=Nao)?", ["s", "c", "n"], default="n")
                if choice_show in ("s", "c"):
                    context_size = 5 if choice_show == "c" else 1
                    snippet = _get_snippet(filepath, f.get("location", ""), context_size)
                    if snippet:
                        print(f"       {snippet}")
                if i < len(findings) and _ask_choice("    Proximo finding?", ["s", "n"], default="s") == "n":
                    break
            if key != crit[-1][0] and _ask_choice("  Proximo criterio?", ["s", "n"], default="s") == "n":
                break

    def show_recommendations() -> None:
        gen = ReportGenerator(filepath, analysis)
        recs = gen._generate_recommendations()
        if not recs:
            print("\n  Nenhuma recomendacao disponivel.")
            return
        print("")
        for i, rec in enumerate(recs, 1):
            prio = rec.get("priority", "MEDIA")
            pc = "\033[91m" if prio == "ALTA" else "\033[93m" if prio == "MEDIA" else "\033[94m"
            print(f"  {pc}[{prio}]\033[0m {rec.get('title', '')}")
            print(f"       {rec.get('description', '')[:120]}")
            action = rec.get("action", rec.get("next_step", ""))
            if action:
                print(f"       \033[92mProxima acao:\033[0m {action[:120]}")
            if i < len(recs) and _ask_choice("  Proxima recomendacao?", ["s", "n"], default="s") == "n":
                break

    def show_metrics() -> None:
        m = analysis.get("metrics", {})
        print(f"\n  Linhas: {m.get('lines_of_code', 0)} ({m.get('code_lines', 0)} codigo, {m.get('comment_lines', 0)} comentarios)")
        print(f"  Classes: {m.get('num_classes', 0)} | Funcoes: {m.get('num_functions', 0)} | Imports: {m.get('num_imports', 0)}")
        print(f"  Complexidade: media {m.get('avg_cyclomatic_complexity', 0)} | max {m.get('max_cyclomatic_complexity', 0)}")
        print(f"  Maintainability Index: {m.get('maintainability_index', 0)} ({m.get('maintainability_grade', 'N/A')})")
        print(f"  Comment ratio: {m.get('comment_ratio', 0)}% (alvo {m.get('comment_ratio_target', 10)}%)")

    nonlocal_state = {"should_save": should_save, "artifact_registry": artifact_registry, "dry_run": dry_run}

    def do_save() -> None:
        if nonlocal_state["should_save"]:
            reg = nonlocal_state["artifact_registry"]
            print(f"\n  Relatorios ja salvos em: {reg.run_root if reg else '?'}")
            return
        out = input("\n  Diretorio para salvar relatorios: ").strip()
        if not out:
            print("  Operacao cancelada.")
            return
        out_path = Path(out)
        out_path.mkdir(parents=True, exist_ok=True)
        new_registry = ArtifactRegistry(filepath, output_dir=str(out_path))
        result = generate_reports(filepath, analysis, artifact_registry=new_registry, generate_html=generate_html)
        if result.get("error"):
            print(f"  Erro: {result['error']}")
        else:
            print(f"  JSON: {result.get('json_report')}")
            print(f"  MD:   {result.get('markdown_report')}")
            if result.get("html_report"):
                print(f"  HTML: {result.get('html_report')}")
            nonlocal_state["should_save"] = True
            nonlocal_state["artifact_registry"] = new_registry

    def do_refactor() -> None:
        config_gen = config.get("generate_tests", True)
        local_tests = config_gen and _ask_user(
            "  Deseja gerar o scaffold de testes unitarios pytest?", default=True
        )
        reg = nonlocal_state["artifact_registry"]

        print("\n  Simulando refatoracao (dry-run)...")
        refactoring_result = refactor_file(
            filepath, dry_run=True,
            output_dir=str(reg.run_root) if reg else None,
            artifact_registry=reg, quiet=True, generate_tests=local_tests,
        )
        if refactoring_result.get("error"):
            print(f"\n  Erro na simulacao: {refactoring_result['error']}")
            return

        changes_detail = (
            refactoring_result.get("phases", {})
            .get("2_refactor", {})
            .get("changes_detail", [])
        )
        if not changes_detail:
            print("\n  Nenhuma alteracao necessaria.")
            return

        by_rule = _group_changes_by_rule(changes_detail)
        selected_rules, cached_diffs = _select_rules(
            filepath, by_rule, reg
        )
        if selected_rules is None:
            return

        if not selected_rules:
            print("\n  Nenhuma regra selecionada. Operacao cancelada.")
            return

        if _ask_user("\n  Deseja aplicar as regras selecionadas ao arquivo original?", default=False):
            _apply_refactor(filepath, reg, selected_rules, local_tests)
        else:
            print("\n  Operacao cancelada. Nenhuma alteracao foi feita no disco.")

    while True:
        choice = show_menu()
        if choice == "1":
            show_critical()
        elif choice == "2":
            show_recommendations()
        elif choice == "3":
            show_metrics()
        elif choice == "4":
            do_save()
        elif choice == "5":
            do_refactor()
        else:
            print("\n  Analise concluida!")
            break
