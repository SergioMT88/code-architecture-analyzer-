"""Pipeline orchestrator — Identification -> Proposition -> Implementation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from code_analyzer.analyzer import run_analysis, prune_criteria
from code_analyzer.analyzer.scoring import production_risk_score
from code_analyzer.artifact_manager import ArtifactRegistry
from code_analyzer.config import load_config
from code_analyzer.history import get_last_matching_snapshot, load_history, save_history_snapshot
from code_analyzer.refactorer import RefactoringOrchestrator, refactor_file
from code_analyzer.report_generator import ReportGenerator, generate_reports


# ------------------------------------------------------------------
# Argument parser
# ------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="code-analyze",
        description="Deep Python architecture analysis with automatic refactoring.",
    )
    p.add_argument("file", help="Python file to analyse")
    p.add_argument("--no-refactor", action="store_true", help="Analyse only, skip refactoring")
    p.add_argument("--no-tests", action="store_true", help="Skip generating pytest unit test scaffold")
    p.add_argument("--dry-run", action="store_true", help="Show what would be done without applying")
    p.add_argument("--interactive", action="store_true", help="Interactive step-by-step mode")
    p.add_argument("--quiet", action="store_true", help="Minimal terminal output")
    p.add_argument("--json", dest="json_mode", action="store_true", help="Machine-readable JSON output")
    p.add_argument("--compact", action="store_true", help="Otimiza a verbosidade do relatorio e mensagens de terminal para economizar tokens")
    p.add_argument("--html", action="store_true", help="Generate visual HTML dashboard")
    p.add_argument("--force", action="store_true", help="Forcar nova analise, ignorando o cache da Lazy Evaluation")
    p.add_argument("--patch-only", action="store_true", help="Gerar apenas arquivos .patch para revisao manual, sem modificar arquivos")
    p.add_argument("--output", dest="output_dir", default=None, metavar="DIR",
                   help="Save reports to DIR (default: terminal only)")
    return p


# ------------------------------------------------------------------
# Terminal UI helpers (output in Portuguese — user-visible)
# ------------------------------------------------------------------

def _score_bar(n: int, total: int = 10, size: int = 10) -> str:
    filled = round(n / max(total, 1) * size)
    fg = 92 if n >= 7 else 93 if n >= 5 else 91
    return f"\033[{fg}m" + "#" * filled + "\033[90m" + "-" * (size - filled) + "\033[0m"


def _grade_color(grade: str) -> str:
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
    artifact_registry: Optional[ArtifactRegistry] = None,
    json_mode: bool = False,
) -> None:
    if json_mode:
        return
    criteria = analysis.get("criteria", {})
    metrics = analysis.get("metrics", {})
    scores = [v.get("score", 0) for v in criteria.values()]
    avg_score = round(sum(scores) / max(1, len(scores)), 1)
    grade = "A" if avg_score >= 9 else "B" if avg_score >= 7 else "C" if avg_score >= 5 else "D"
    critical = [(k, v) for k, v in criteria.items() if v.get("score", 10) < 5]
    warnings = [(k, v) for k, v in criteria.items() if 5 <= v.get("score", 10) < 7]
    total_findings = sum(len(v.get("findings", [])) for v in criteria.values())
    mi = metrics.get("maintainability_index", 0)
    mg = metrics.get("maintainability_grade", "N/A")

    bar = _score_bar(avg_score)
    gc = _grade_color(grade)
    print(f"\n  \033[1m{bar}  {avg_score}/10  ({gc}{grade}\033[0m\033[1m)\033[0m  \033[90m{Path(filepath).name}\033[0m")
    print(f"  \033[90m{'-'*50}\033[0m")
    risk = analysis.get("production_risk", {})
    risk_score = risk.get("score", 0)
    risk_label = risk.get("label", "Desconhecido")
    rc = "\033[91m" if risk_label == "Critico" else "\033[93m" if risk_label == "Risco" else "\033[92m"
    print(
        f"  \033[90mMI:\033[0m {mi} ({mg})  "
        f"Risco de Producao: {rc}{risk_score}/100 ({risk_label})\033[0m"
    )
    print(
        f"  \033[91m! {len(critical)} critico(s)\033[0m  "
        f"\033[93m* {len(warnings)} aviso(s)\033[0m  "
        f"\033[94m. {total_findings} finding(s)\033[0m"
    )


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
            score = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    {_score_bar(score)} \033[91m{key}\033[0m ({n} problemas)")
            for finding in val.get("findings", [])[:2]:
                loc = finding.get("location", "")
                iss = finding.get("issue", "")[:80]
                print(f"      \033[90m[{loc}]\033[0m {iss}")

    if warnings_list:
        print(f"\n  \033[1m\033[93m* AVISO ({len(warnings_list)} criterios):\033[0m")
        for key, val in warnings_list:
            score = val.get("score", 0)
            n = len(val.get("findings", []))
            print(f"    {_score_bar(score)} \033[93m{key}\033[0m ({n} problemas)")

    ok_count = sum(1 for v in criteria.values() if v.get("score", 10) >= 7)
    if ok_count:
        print(f"  \033[92m. {ok_count} criterios OK\033[0m")

    tool_findings = analysis.get("tool_findings", {})
    total_tools = tool_findings.get("total", 0)
    if total_tools:
        print(
            f"\n  \033[94mFerramentas externas:\033[0m {total_tools} ocorrencias "
            f"(ruff: {len(tool_findings.get('ruff', []))}, "
            f"pylint: {len(tool_findings.get('pylint', []))})"
        )
    for w in analysis.get("tool_warnings", []):
        print(f"  \033[93m!\033[0m {w}")


# ------------------------------------------------------------------
# Interactive menu (user-visible terminal output in Portuguese)
# ------------------------------------------------------------------

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
    except Exception:
        return ""


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
        local_tests = False
        if config_gen:
            local_tests = _ask_user("  Deseja gerar o scaffold de testes unitarios pytest?", default=True)
        reg = nonlocal_state["artifact_registry"]

        print("\n  Simulando refatoracao (dry-run)...")
        refactoring_result = refactor_file(
            filepath,
            dry_run=True,
            output_dir=str(reg.run_root) if reg else None,
            artifact_registry=reg,
            quiet=True,
            generate_tests=local_tests,
        )
        if refactoring_result.get("error"):
            print(f"\n  Erro na simulacao: {refactoring_result['error']}")
            return

        phases = refactoring_result.get("phases", {})
        phase2 = phases.get("2_refactor", {})
        changes_detail = phase2.get("changes_detail", [])
        if not changes_detail:
            print("\n  Nenhuma alteracao necessaria.")
            return

        # Group changes by rule type
        by_rule: Dict[str, List[Dict[str, Any]]] = {}
        for ch in changes_detail:
            rule = ch.get("type", "unknown")
            by_rule.setdefault(rule, []).append(ch)

        rule_labels = {
            "docstring": "Adicionar docstring de modulo",
            "duplicate_import": "Remover imports duplicados",
            "unused_import": "Remover imports nao usados",
            "useless_fstring": "Corrigir f-strings sem placeholders",
            "ambiguous_variable": "Renomear variaveis ambiguas (l, I, O)",
        }

        selected_rules: List[str] = []
        cached_diffs: Dict[str, str] = {}
        for rule, items in by_rule.items():
            label = rule_labels.get(rule, rule)
            changes = items
            preview_lines = "\n".join(f"      {ch.get('description', '')[:80]}" for ch in changes[:3])
            if len(changes) > 3:
                preview_lines += f"\n      ... +{len(changes) - 3} alteracao(oes)"

            while True:
                print(f"\n  {label}? ({len(changes)} alteracao(oes))")
                print(preview_lines)
                ans = _ask_choice("  [a]plicar, [p]ular, [v]er diff, [s]air", ["a", "p", "v", "s"], default="a")
                if ans == "s":
                    print("\n  Operacao cancelada. Nenhuma alteracao foi feita no disco.")
                    return
                if ans == "v":
                    if rule not in cached_diffs:
                        diff_result = refactor_file(
                            filepath, dry_run=True,
                            output_dir=str(reg.run_root) if reg else None,
                            artifact_registry=reg, quiet=True,
                            generate_tests=False,
                            enabled_rules=[rule],
                        )
                        cached_diffs[rule] = diff_result.get("diff", "Sem diff disponivel.")
                    diff_text = cached_diffs[rule]
                    print(f"\n  --- Diff para: {label} ---")
                    diff_lines_list = diff_text.split("\n")
                    for j in range(0, len(diff_lines_list), 20):
                        chunk = diff_lines_list[j:j+20]
                        for dl in chunk:
                            print(f"  {dl}")
                        if j + 20 < len(diff_lines_list):
                            input("\n  [Enter] para continuar...")
                    continue
                if ans == "a":
                    selected_rules.append(rule)
                    break
                if ans == "p":
                    break

        if not selected_rules:
            print("\n  Nenhuma regra selecionada. Operacao cancelada.")
            return

        if _ask_user("\n  Deseja aplicar as regras selecionadas ao arquivo original?", default=False):
            print("\n  Aplicando refatoracao real...")
            real_result = refactor_file(
                filepath,
                dry_run=False,
                output_dir=str(reg.run_root) if reg else None,
                artifact_registry=reg,
                quiet=False,
                generate_tests=local_tests,
                enabled_rules=selected_rules,
            )
            if real_result.get("error"):
                print(f"\n  Erro ao aplicar: {real_result['error']}")
            else:
                print("\n  Correcoes aplicadas com sucesso!")
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


# ------------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------------

def run_pipeline(args: argparse.Namespace) -> int:
    filepath = args.file
    no_refactor = args.no_refactor
    no_tests = args.no_tests
    dry_run = args.dry_run
    interactive = args.interactive
    quiet = args.quiet
    json_mode = args.json_mode
    generate_html = args.html
    output_dir: Optional[str] = args.output_dir
    compact = getattr(args, "compact", False)

    config = load_config(filepath, quiet=quiet or json_mode)
    if dry_run:
        config["dry_run"] = True
    if interactive:
        config["interactive"] = True
    if quiet or json_mode:
        config["quiet"] = True
    if compact:
        config["compact"] = True
    if output_dir:
        config["output_dir"] = output_dir

    structured_outputs = config.get("structured_outputs", True)
    generate_tests = config.get("generate_tests", True)
    if no_tests:
        generate_tests = False
    config["generate_tests"] = generate_tests
    patch_only = getattr(args, "patch_only", False)
    if patch_only:
        dry_run = True
    should_save = output_dir is not None
    artifact_registry: Optional[ArtifactRegistry] = None
    if should_save:
        artifact_registry = ArtifactRegistry(
            filepath, output_dir=output_dir, structured_outputs=structured_outputs
        )

    if not json_mode:
        if quiet:
            print("\nCODE ARCHITECTURE ANALYZER v2.1.5")
            print(f"Arquivo: {filepath}")
            if should_save:
                print(f"Saida: {artifact_registry.run_root}")  # type: ignore[union-attr]
            if dry_run:
                print("Modo: DRY-RUN")
            if interactive:
                print("Modo: INTERATIVO")
        else:
            print("\n" + "=" * 70)
            print("  CODE ARCHITECTURE ANALYZER v2.1.5 - PIPELINE COMPLETO")
            print(f"  Arquivo: {filepath}")
            if should_save:
                print(f"  Saida: {artifact_registry.run_root}")  # type: ignore[union-attr]
            else:
                print("  Saida: apenas terminal (use --output para salvar relatorios)")
            if dry_run:
                print("  MODO: DRY-RUN (nenhum arquivo sera modificado)")
            if patch_only:
                print("  MODO: PATCH-ONLY (gerando apenas .patch para revisao manual)")
            if interactive:
                print("  MODO: INTERATIVO")
            print("=" * 70)

    # Lazy Evaluation: skip re-analysis if file content hasn't changed since last run
    force = getattr(args, "force", False)
    from_cache = False
    analysis: Optional[Dict[str, Any]] = None
    if not force:
        try:
            code = Path(filepath).read_text(encoding="utf-8")
            cached = get_last_matching_snapshot(filepath, code)
            if cached is not None:
                if not json_mode:
                    print("\n  [Lazy Evaluation] Arquivo nao alterado. Reutilizando analise do historico.")
                analysis = cached
                from_cache = True
        except Exception:
            pass

    if analysis is None:
        # Phase 1: Identification
        print_phase(
            "FASE 1 - IDENTIFICACAO (3 micro-fases)",
            "1a: AST Scanning | 1b: Pylint | 1c: Ruff",
            quiet=quiet, json_mode=json_mode,
        )

        analysis = run_analysis(filepath, config)

    if analysis is None or not analysis.get("success", False):
        if json_mode:
            print(json.dumps(
                {"success": False, "file": filepath, "error": analysis.get("error")},
                ensure_ascii=True, default=str,
            ))
        else:
            print(f"\nErro: {analysis.get('error')}")
        return 1

    # Compute production risk score
    analysis["production_risk"] = production_risk_score(
        analysis.get("metrics", {}),
        analysis.get("criteria", {}),
        analysis.get("test_analysis", {}),
    )

    print_executive_summary(filepath, analysis, artifact_registry, json_mode=json_mode)
    print_findings_summary(analysis, quiet=config.get("quiet", False), json_mode=json_mode)
    if not json_mode:
        print("\n  Fase 1 concluida!")

    # Generate reports if --output or --json
    report_files: Dict[str, Any] = {}
    if should_save or json_mode:
        report_files = generate_reports(
            filepath,
            analysis,
            output_dir=output_dir if should_save else None,
            artifact_registry=artifact_registry,
            generate_html=generate_html,
        )
        if report_files.get("error"):
            if json_mode:
                print(json.dumps(
                    {"success": False, "file": filepath, "error": report_files.get("error"),
                     "report_files": report_files, "analysis": analysis},
                    ensure_ascii=True, default=str,
                ))
            else:
                print(f"\nErro ao gerar relatorios: {report_files.get('error')}")
                if report_files.get("log_file"):
                    print(f"  Log: {report_files.get('log_file')}")
            return 1

    if not json_mode and should_save:
        print("\n  Gerando relatorios...")
        print(f"  JSON:  {report_files.get('json_report')}")
        print(f"  MD:    {report_files.get('markdown_report')}")
        if report_files.get("html_report"):
            print(f"  HTML:  {report_files.get('html_report')}")
        if report_files.get("manifest"):
            print(f"  Manifest: {report_files.get('manifest')}")

    # Phase 2: Proposition + optional interactive menu
    refactoring_result: Optional[Dict[str, Any]] = None
    if interactive and not json_mode:
        interactive_menu(
            filepath, analysis, config, artifact_registry,
            should_save, dry_run, no_refactor, generate_html,
        )
    else:
        print_phase(
            "FASE 2 - PROPOSICAO (2 micro-fases)",
            "2a: Identificar problemas | 2b: Sugerir solucoes",
            quiet=quiet, json_mode=json_mode,
        )
        all_findings = [
            {"criterion": key, **f}
            for key, value in analysis.get("criteria", {}).items()
            for f in value.get("findings", [])
        ]
        if all_findings and not json_mode:
            print(f"\n  {len(all_findings)} problema(s) identificado(s):\n")
            max_findings = 3 if config.get("quiet") else 5
            is_compact = config.get("compact", False)
            for i, finding in enumerate(all_findings[:max_findings], 1):
                if is_compact:
                    print(f"  {i}. [{finding['criterion']}] [{finding['location']}] {finding['issue'][:120]}")
                    sug = finding.get("suggestion", "")
                    if sug:
                        print(f"     -> {sug[:120]}")
                else:
                    print(f"  {i}. [{finding['criterion']}] {finding['location']}")
                    print(f"     Problema: {finding['issue'][:100]}")
                    sug = finding.get("suggestion", "")
                    if sug:
                        print(f"     Sugestao: {sug[:100]}")
        elif not json_mode:
            print("\n  Nenhum problema critico encontrado automaticamente.")
        if not json_mode:
            print("\n  Fase 2 concluida!")

        # Processamento do histórico
        if not from_cache:
            # 1. Carregar histórico anterior
            previous_runs = load_history(filepath)
            if previous_runs and not json_mode:
                latest_run = previous_runs[-1]
                regressions = []
                
                current_criteria = analysis.get("criteria", {})
                old_scores = latest_run.get("scores", {})
                for crit_name, crit_data in current_criteria.items():
                    if crit_name in old_scores:
                        old_val = old_scores[crit_name]
                        new_val = crit_data.get("score", 10.0)
                        if new_val < old_val:
                            regressions.append((crit_name, old_val, new_val))
                
                if regressions:
                    print("\n  \033[93m⚠️  ALERTA DE REGRESSÃO DE ARQUITETURA:\033[0m")
                    for crit_name, old_val, new_val in regressions:
                        print(f"    - O critério {crit_name} piorou de {old_val:.1f} para {new_val:.1f}!")
                    print()
                    
            # 2. Salvar a execução atual no histórico
            save_history_snapshot(filepath, analysis)

        # Phase 3: Implementation
        if no_refactor:
            if not json_mode:
                print("\n  (--no-refactor: fase de implementacao de refatoracao ignorada)")
            if should_save and generate_tests:
                if not quiet and not json_mode:
                    print("  Gerando scaffold de testes...")
                orch = RefactoringOrchestrator(
                    filepath,
                    dry_run=dry_run,
                    output_dir=output_dir,
                    structured_outputs=structured_outputs,
                    artifact_registry=artifact_registry,
                    quiet=True,
                    generate_tests=True,
                )
                test_result = orch.phase3_tests()
                if refactoring_result is None:
                    refactoring_result = {"phases": {}}
                refactoring_result["phases"]["3_tests"] = test_result
        else:
            print_phase(
                "FASE 3 - IMPLEMENTACAO (5 micro-fases)",
                "3a: Setup | 3b: Refactor | 3c: Tests | 3d: Format | 3e: Validate",
                quiet=quiet, json_mode=json_mode,
            )
            if dry_run and not json_mode:
                print("\n  MODO DRY-RUN: mostrando o que seria feito...\n")

            refactoring_result = refactor_file(
                filepath,
                dry_run=dry_run,
                output_dir=output_dir if should_save else None,
                structured_outputs=structured_outputs,
                artifact_registry=artifact_registry,
                quiet=quiet,
                generate_tests=generate_tests,
            )

            if refactoring_result.get("error"):
                if json_mode:
                    print(json.dumps(
                        {"success": False, "file": filepath,
                         "error": refactoring_result.get("error"), "report_files": report_files},
                        ensure_ascii=True, default=str,
                    ))
                else:
                    print(f"\n  Erro: {refactoring_result.get('error')}")
                return 1

            diff = refactoring_result.get("diff", "")
            if diff and diff != "Sem alteracoes." and not json_mode:
                print("\n  Diff das alteracoes:\n")
                for line in diff.split("\n")[:20]:
                    print(f"  {line}")

            if not json_mode:
                print("\n  Fase 3 concluida!")

    # Final summary
    if json_mode:
        payload: Dict[str, Any] = {
            "success": True,
            "file": filepath,
            "mode": {
                "no_refactor": no_refactor,
                "dry_run": dry_run,
                "interactive": interactive,
                "quiet": quiet,
            },
            "artifact_root": str(artifact_registry.run_root) if artifact_registry else None,
            "analysis": prune_criteria(analysis),
            "report_files": report_files,
        }
        if refactoring_result is not None:
            payload["refactoring"] = refactoring_result
        print(json.dumps(payload, ensure_ascii=True, default=str))
        return 0

    if quiet:
        print("\nPIPELINE CONCLUIDO")
    else:
        print("\n" + "=" * 70)
        print("  PIPELINE CONCLUIDO!")
        print("=" * 70)

    stem = Path(filepath).stem
    print("\n\033[1mResumo final\033[0m")
    if should_save:
        print(f"  \033[94mJSON:\033[0m  {report_files.get('json_report', stem + '_analysis.json')}")
        print(f"  \033[94mMD:\033[0m    {report_files.get('markdown_report', stem + '_report.md')}")
        if report_files.get("html_report"):
            print(f"  \033[94mHTML:\033[0m  {report_files.get('html_report')}")
        if report_files.get("manifest"):
            print(f"  Manifest: {report_files.get('manifest')}")
    if not no_refactor and not dry_run:
        print(f"  Arquivo modificado: {filepath}")
        if artifact_registry:
            print(f"  Backup: {artifact_registry.backups_dir / f'{stem}_backup.py'}")
    print()
    return 0


def main() -> None:
    parser = build_parser()
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
