"""Pipeline core — Identification → Proposition → Implementation."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

from code_analyzer import __version__
from code_analyzer.analyzer import run_analysis, prune_criteria
from code_analyzer.analyzer.scoring import production_risk_score
from code_analyzer.analyzer.test_pain import analyze_test_pain
from code_analyzer.artifact_manager import ArtifactRegistry
from code_analyzer.config import load_config
from code_analyzer.gate import check_min_score
from code_analyzer.history import (
    check_roi_diminishing,
    get_last_matching_snapshot,
    load_history,
    save_history_snapshot,
)
from code_analyzer.interactive import interactive_menu
from code_analyzer.limits import MAX_DIFF_LINES_TERMINAL
from code_analyzer.pattern_advisor import get_pattern_advice
from code_analyzer.project_context import compute_priority_index
from code_analyzer.refactorer import RefactoringOrchestrator, refactor_file
from code_analyzer.report_generator import generate_reports
from code_analyzer.terminal_ui import (
    ScoreBundle,
    _compute_score_bundle,
    _first_run_check,
    print_equivalence_confidence,
    print_executive_summary,
    print_findings_summary,
    print_next_steps,
    print_pattern_advice,
    print_phase,
    print_priority_index,
    print_project_context,
    print_welcome,
)


_DEFAULT_HTML_DIR = Path.home() / ".code-analyzer" / "reports"


@dataclass
class PipelineContext:
    """Shared state passed through all pipeline phases."""
    filepath: str
    no_refactor: bool
    no_tests: bool
    dry_run: bool
    interactive: bool
    quiet: bool
    json_mode: bool
    generate_html: bool
    output_dir: Optional[str]
    compact: bool
    min_score_arg: Optional[float]
    patch_only: bool
    force: bool
    config: Dict[str, Any]
    should_save: bool
    artifact_registry: Optional[ArtifactRegistry]
    generate_tests: bool
    auto_html: bool = False
    from_cache: bool = False
    report_files: Dict[str, Any] = field(default_factory=dict)


def _setup(args: argparse.Namespace) -> PipelineContext:
    """Extract args, load config, setup artifacts, print header."""
    filepath = args.file
    no_refactor = args.no_refactor
    no_tests = args.no_tests
    dry_run = args.dry_run
    interactive = args.interactive
    quiet = args.quiet
    json_mode = args.json_mode
    no_html = getattr(args, "no_html", False)
    generate_html = not no_html
    output_dir: Optional[str] = args.output_dir
    compact = getattr(args, "compact", False)
    min_score_arg: Optional[float] = getattr(args, "min_score", None)
    force = getattr(args, "force", False)
    patch_only = getattr(args, "patch_only", False)
    if getattr(args, "no_cache", False) or force:
        import os as _os
        _os.environ["CODE_ANALYZER_NO_CACHE"] = "1"

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

    generate_tests = config.get("generate_tests", True)
    if no_tests:
        generate_tests = False
    config["generate_tests"] = generate_tests
    if patch_only:
        dry_run = True

    should_save = output_dir is not None
    auto_html = generate_html and not should_save and not json_mode
    artifact_registry: Optional[ArtifactRegistry] = None
    if should_save:
        artifact_registry = ArtifactRegistry(
            filepath, output_dir=output_dir, structured_outputs=config.get("structured_outputs", True)
        )

    if not json_mode:
        if quiet:
            print(f"\nCODE ARCHITECTURE ANALYZER v{__version__}")
            print(f"Arquivo: {filepath}")
            if should_save:
                print(f"Saida: {artifact_registry.run_root}")
            if dry_run:
                print("Modo: DRY-RUN")
            if interactive:
                print("Modo: INTERATIVO")
        else:
            print("\n" + "=" * 70)
            print(f"  CODE ARCHITECTURE ANALYZER v{__version__} - PIPELINE COMPLETO")
            print(f"  Arquivo: {filepath}")
            if should_save:
                print(f"  Saida: {artifact_registry.run_root}")
            elif auto_html:
                print(f"  Saida: HTML em {_DEFAULT_HTML_DIR}")
            else:
                print("  Saida: apenas terminal (use --output para salvar relatorios)")
            if dry_run:
                print("  MODO: DRY-RUN (nenhum arquivo sera modificado)")
            if patch_only:
                print("  MODO: PATCH-ONLY (gerando apenas .patch para revisao manual)")
            if interactive:
                print("  MODO: INTERATIVO")
            print("=" * 70)

    return PipelineContext(
        filepath=filepath,
        no_refactor=no_refactor,
        no_tests=no_tests,
        dry_run=dry_run,
        interactive=interactive,
        quiet=quiet,
        json_mode=json_mode,
        generate_html=generate_html,
        output_dir=output_dir,
        compact=compact,
        min_score_arg=min_score_arg,
        patch_only=patch_only,
        force=force,
        config=config,
        should_save=should_save,
        auto_html=auto_html,
        artifact_registry=artifact_registry,
        generate_tests=generate_tests,
    )


def _phase1_identification(ctx: PipelineContext) -> tuple:
    """Lazy eval check → run_analysis → compute risk/priority scores → return (analysis, sb)."""
    from_cache = False
    analysis: Optional[Dict[str, Any]] = None

    if not ctx.force:
        try:
            code = Path(ctx.filepath).read_text(encoding="utf-8")
            cached = get_last_matching_snapshot(ctx.filepath, code)
            if cached is not None:
                if not ctx.json_mode:
                    print("\n  [Lazy Evaluation] Arquivo nao alterado. Reutilizando analise do historico.")
                analysis = cached
                from_cache = True
        except Exception:
            _log.debug("Lazy evaluation cache lookup failed for %s", ctx.filepath, exc_info=True)

    ctx.from_cache = from_cache

    if analysis is None:
        print_phase(
            "FASE 1 - IDENTIFICACAO (3 micro-fases)",
            "1a: AST Scanning | 1b: Ruff (PL ruleset) | 1c: Metricas",
            quiet=ctx.quiet, json_mode=ctx.json_mode,
        )
        analysis = run_analysis(ctx.filepath, ctx.config)

    if analysis is None or not analysis.get("success", False):
        return (analysis, None)

    analysis["production_risk"] = production_risk_score(
        analysis.get("metrics", {}),
        analysis.get("criteria", {}),
        analysis.get("test_analysis", {}),
        analysis.get("test_pain"),
    )

    pctx = analysis.get("project_context", {})
    coverage_pct = analysis.get("test_analysis", {}).get("estimated_coverage", 0)
    analysis["priority_index"] = compute_priority_index(
        fan_in=pctx.get("fan_in", 0),
        commit_count=pctx.get("commit_count", 0),
        coverage_pct=float(coverage_pct),
    )

    # v5.0.0: Test Pain metrics
    analysis["test_pain"] = analyze_test_pain(ctx.filepath)

    sb = print_executive_summary(ctx.filepath, analysis, ctx.artifact_registry, json_mode=ctx.json_mode)
    print_findings_summary(analysis, quiet=ctx.config.get("quiet", False), json_mode=ctx.json_mode)

    if not ctx.json_mode:
        print_project_context(analysis, ctx.filepath)
        if not ctx.config.get("quiet"):
            print_priority_index(analysis)
            advice = get_pattern_advice(analysis)
            print_pattern_advice(advice)
            print_equivalence_confidence(analysis)
        print("\n  Fase 1 concluida!")

    # Write equivalence test files
    purity_map = analysis.get("purity_map", {})
    if purity_map and ctx.should_save and not ctx.no_refactor and not ctx.json_mode:
        try:
            from code_analyzer.analyzer.equivalence import write_equivalence_tests
            assert ctx.artifact_registry is not None
            eq_out_dir = ctx.artifact_registry.tests_dir
            written = write_equivalence_tests(ctx.filepath, purity_map, str(eq_out_dir))
            if written and not ctx.quiet:
                print(f"\n  [Equivalencia] {len(written)} teste(s) de equivalencia gerado(s) em:")
                for p in written[:3]:
                    print(f"    {p}")
        except Exception:
            _log.debug("Equivalence test generation failed for %s", ctx.filepath, exc_info=True)

    return (analysis, sb)


def _phase2_proposition(ctx: PipelineContext, analysis: Dict, sb: ScoreBundle) -> Optional[Dict]:
    """Generate reports, interactive menu or auto-display findings, save history."""
    report_files: Dict[str, Any] = {}
    if ctx.should_save or ctx.json_mode:
        report_files = generate_reports(
            ctx.filepath,
            analysis,
            output_dir=ctx.output_dir if ctx.should_save else None,
            artifact_registry=ctx.artifact_registry,
            generate_html=ctx.generate_html,
        )
    elif ctx.auto_html:
        report_files = generate_reports(
            ctx.filepath,
            analysis,
            output_dir=str(_DEFAULT_HTML_DIR),
            generate_html=True,
            html_only=True,
        )

    ctx.report_files = report_files

    if report_files.get("error"):
        if ctx.json_mode:
            print(json.dumps(
                {"success": False, "file": ctx.filepath, "error": report_files.get("error"),
                 "report_files": report_files, "analysis": analysis},
                ensure_ascii=True, default=str,
            ))
        else:
            print(f"\nErro ao gerar relatorios: {report_files.get('error')}")
            if report_files.get("log_file"):
                print(f"  Log: {report_files.get('log_file')}")
        return {"error": report_files.get("error"), "report_files": report_files}

    if not ctx.json_mode and ctx.should_save:
        print("\n  Gerando relatorios...")
        print(f"  JSON:  {report_files.get('json_report')}")
        print(f"  MD:    {report_files.get('markdown_report')}")
        if report_files.get("html_report"):
            print(f"  HTML:  {report_files.get('html_report')}")
        if report_files.get("manifest"):
            print(f"  Manifest: {report_files.get('manifest')}")

    refactoring_result: Optional[Dict[str, Any]] = None

    if ctx.interactive and not ctx.json_mode:
        interactive_menu(
            ctx.filepath, analysis, ctx.config, ctx.artifact_registry,
            ctx.should_save, ctx.dry_run, ctx.no_refactor, ctx.generate_html,
        )
    else:
        print_phase(
            "FASE 2 - PROPOSICAO (2 micro-fases)",
            "2a: Identificar problemas | 2b: Sugerir solucoes",
            quiet=ctx.quiet, json_mode=ctx.json_mode,
        )
        all_findings = [
            {"criterion": key, **f}
            for key, value in analysis.get("criteria", {}).items()
            for f in value.get("findings", [])
        ]
        if all_findings and not ctx.json_mode:
            print(f"\n  {len(all_findings)} problema(s) identificado(s):\n")
            max_findings = 3 if ctx.config.get("quiet") else 5
            is_compact = ctx.config.get("compact", False)
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
        elif not ctx.json_mode:
            print("\n  Nenhum problema critico encontrado automaticamente.")
        if not ctx.json_mode:
            print("\n  Fase 2 concluida!")

        if not ctx.from_cache:
            previous_runs = load_history(ctx.filepath)
            if previous_runs and not ctx.json_mode:
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
                    print("\n  \033[93m[!] ALERTA DE REGRESSAO DE ARQUITETURA:\033[0m")
                    for crit_name, old_val, new_val in regressions:
                        print(f"    - O critério {crit_name} piorou de {old_val:.1f} para {new_val:.1f}!")
                    print()

            roi = check_roi_diminishing(ctx.filepath)
            if roi.get("roi_diminishing") and not ctx.json_mode:
                print(f"\n  \033[93m[ROI]\033[0m {roi['message']}")

            save_history_snapshot(ctx.filepath, analysis)

    return refactoring_result


def _phase3_implementation(
    ctx: PipelineContext, analysis: Dict, refactoring_result: Optional[Dict]
) -> Optional[Dict]:
    """Run refactoring (or skip if no_refactor), return updated refactoring_result."""
    if ctx.no_refactor:
        if not ctx.json_mode:
            print("\n  (--no-refactor: fase de implementacao de refatoracao ignorada)")
        if ctx.should_save and ctx.generate_tests:
            if not ctx.quiet and not ctx.json_mode:
                print("  Gerando scaffold de testes...")
            orch = RefactoringOrchestrator(
                ctx.filepath, dry_run=ctx.dry_run, output_dir=ctx.output_dir,
                structured_outputs=ctx.config.get("structured_outputs", True),
                artifact_registry=ctx.artifact_registry, quiet=True, generate_tests=True,
            )
            test_result = orch.phase3_tests()
            if refactoring_result is None:
                refactoring_result = {"phases": {}}
            refactoring_result["phases"]["3_tests"] = test_result
        return refactoring_result

    print_phase(
        "FASE 3 - IMPLEMENTACAO (5 micro-fases)",
        "3a: Setup | 3b: Refactor | 3c: Tests | 3d: Format | 3e: Validate",
        quiet=ctx.quiet, json_mode=ctx.json_mode,
    )
    if ctx.dry_run and not ctx.json_mode:
        print("\n  MODO DRY-RUN: mostrando o que seria feito...\n")

    refactoring_result = refactor_file(
        ctx.filepath, dry_run=ctx.dry_run,
        output_dir=ctx.output_dir if ctx.should_save else None,
        structured_outputs=ctx.config.get("structured_outputs", True),
        artifact_registry=ctx.artifact_registry,
        quiet=ctx.quiet, generate_tests=ctx.generate_tests,
    )

    if refactoring_result.get("error"):
        if ctx.json_mode:
            print(json.dumps(
                {"success": False, "file": ctx.filepath,
                 "error": refactoring_result.get("error"), "report_files": ctx.report_files},
                ensure_ascii=True, default=str,
            ))
        else:
            print(f"\n  Erro: {refactoring_result.get('error')}")
        return None

    diff = refactoring_result.get("diff", "")
    if diff and diff != "Sem alteracoes." and not ctx.json_mode:
        print("\n  Diff das alteracoes:\n")
        for line in diff.split("\n")[:MAX_DIFF_LINES_TERMINAL]:
            safe = line.encode("cp1252", errors="replace").decode("cp1252")
            print(f"  {safe}")

    if not ctx.json_mode:
        print("\n  Fase 3 concluida!")

    return refactoring_result


def _finalize(
    ctx: PipelineContext, analysis: Dict, sb: ScoreBundle, ref_result: Optional[Dict],
) -> int:
    """Print JSON/quiet summary, check min-score gate, return exit code."""
    if ctx.json_mode:
        payload: Dict[str, Any] = {
            "success": True,
            "file": ctx.filepath,
            "mode": {
                "no_refactor": ctx.no_refactor,
                "dry_run": ctx.dry_run,
                "interactive": ctx.interactive,
                "quiet": ctx.quiet,
            },
            "artifact_root": str(ctx.artifact_registry.run_root) if ctx.artifact_registry else None,
            "analysis": prune_criteria(analysis),
            "report_files": ctx.report_files,
        }
        if ref_result is not None:
            payload["refactoring"] = ref_result
        print(json.dumps(payload, ensure_ascii=True, default=str))
        return check_min_score(sb, ctx.min_score_arg, ctx.config, quiet=True, json_mode=True)

    if ctx.quiet:
        print("\nPIPELINE CONCLUIDO")
    else:
        print("\n" + "=" * 70)
        print("  PIPELINE CONCLUIDO!")
        print("=" * 70)

    stem = Path(ctx.filepath).stem
    print("\n\033[1mResumo final\033[0m")
    if ctx.should_save:
        print(f"  \033[94mJSON:\033[0m  {ctx.report_files.get('json_report', stem + '_analysis.json')}")
        print(f"  \033[94mMD:\033[0m    {ctx.report_files.get('markdown_report', stem + '_report.md')}")
        if ctx.report_files.get("html_report"):
            print(f"  \033[94mHTML:\033[0m  {ctx.report_files.get('html_report')}")
        if ctx.report_files.get("manifest"):
            print(f"  Manifest: {ctx.report_files.get('manifest')}")
    if not ctx.no_refactor and not ctx.dry_run:
        print(f"  Arquivo modificado: {ctx.filepath}")
        if ctx.artifact_registry:
            print(f"  Backup: {ctx.artifact_registry.backups_dir / f'{stem}_backup.py'}")
    if not ctx.quiet:
        from code_analyzer.terminal_ui import print_noisy_notice
        print_noisy_notice(analysis.get("criteria", {}))
    html_path = ctx.report_files.get("html_report")
    if html_path and not ctx.json_mode:
        import webbrowser
        from code_analyzer.i18n import t
        webbrowser.open(f"file:///{Path(html_path).resolve().as_posix()}")
        print(f"  \033[94m[HTML]\033[0m {t('opening_browser')}")
    if not ctx.quiet and not ctx.json_mode:
        il_has = _il_has_data(ctx.filepath)
        print_next_steps(analysis, sb, il_has)
    print()
    return check_min_score(sb, ctx.min_score_arg, ctx.config, quiet=ctx.quiet, json_mode=ctx.json_mode)


def _il_has_data(filepath: str) -> bool:
    """Return True if the project already has Intent Learning answers."""
    try:
        from code_analyzer.project_context import _find_project_root
        root = _find_project_root(Path(filepath))
        if root is None:
            return False
        intent_file = Path(root) / ".analyzer_intent.json"
        if not intent_file.exists():
            return False
        import json as _json
        data = _json.loads(intent_file.read_text(encoding="utf-8"))
        return len(data.get("answers", {})) > 0
    except Exception:
        return False


def _intent_learning_phase(ctx: PipelineContext, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """IL3: apply stored intents + optionally run conversational Q&A session.

    Skipped entirely in JSON mode or when project root cannot be resolved.
    Questions are only asked when running in a TTY and not --quiet.
    """
    if ctx.json_mode:
        return analysis
    try:
        from pathlib import Path as _Path
        from code_analyzer.intent_store import IntentStore
        from code_analyzer.intent_session import run_intent_session
        from code_analyzer.project_context import _find_project_root
        project_root = _find_project_root(_Path(ctx.filepath))
        if project_root is None:
            return analysis
        intent_store = IntentStore(str(project_root))
        ask = not ctx.quiet
        updated = run_intent_session(
            ctx.filepath,
            analysis["criteria"],
            intent_store,
            limit=3,
            ask_questions=ask,
        )
        analysis = {**analysis, "criteria": updated}
        from code_analyzer.intent_report import write_intent_md
        write_intent_md(intent_store, project_root)
    except Exception:
        _log.debug("Intent learning phase failed for %s", ctx.filepath, exc_info=True)
    return analysis


def _print_intent_delta(sb_before: ScoreBundle, sb_after: ScoreBundle, analysis: Dict) -> None:
    """Print a compact notice when intent learning changed the score."""
    silenced_count = sb_before.total_findings - sb_after.total_findings
    if silenced_count <= 0:
        return
    noisy = [n for n, v in analysis.get("criteria", {}).items() if v.get("noisy")]
    from code_analyzer.terminal_ui import score_bar, grade_color
    score_str = (
        f"{score_bar(int(sb_after.avg_score))}  "
        f"\033[1m{sb_after.avg_score}/10\033[0m  "
        f"({grade_color(sb_after.grade)}{sb_after.grade}\033[0m)"
    )
    print(f"\n  \033[1m\033[94m[Intent Learning]\033[0m "
          f"{silenced_count} finding(s) silenciado(s) por decisoes registradas")
    if noisy:
        print(f"  \033[90mDetectores em modo informacional: {', '.join(noisy)}\033[0m")
    print(f"  Score atualizado: {score_str}  \033[90m({sb_before.avg_score} -> {sb_after.avg_score})\033[0m")


def run_pipeline(args: argparse.Namespace) -> int:
    """Orchestrate the full 3-phase analysis pipeline."""
    if not getattr(args, "json_mode", False) and not getattr(args, "quiet", False):
        if _first_run_check():
            print_welcome()
    ctx = _setup(args)
    analysis, sb = _phase1_identification(ctx)
    if analysis is None:
        return 1
    analysis = _intent_learning_phase(ctx, analysis)
    sb_after = _compute_score_bundle(analysis)
    if not ctx.json_mode and not ctx.quiet:
        _print_intent_delta(sb, sb_after, analysis)
    sb = sb_after
    ref_result = _phase2_proposition(ctx, analysis, sb)
    ref_result = _phase3_implementation(ctx, analysis, ref_result)
    return _finalize(ctx, analysis, sb, ref_result)
