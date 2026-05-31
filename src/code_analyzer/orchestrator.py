"""Pipeline orchestrator entry point — argument parsing and dispatch."""
from __future__ import annotations

import argparse
import sys

from code_analyzer.pipeline import run_pipeline


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
    p.add_argument("--no-html", dest="no_html", action="store_true", help="Desabilitar geracao de HTML")
    p.add_argument("--force", action="store_true", help="Forcar nova analise, ignorando o cache da Lazy Evaluation")
    p.add_argument("--no-cache", dest="no_cache", action="store_true",
                   help="Desabilita o cache de criteria por hash de arquivo (forca re-execucao dos detectores)")
    p.add_argument("--patch-only", action="store_true", help="Gerar apenas arquivos .patch para revisao manual, sem modificar arquivos")
    p.add_argument("--output", dest="output_dir", default=None, metavar="DIR",
                   help="Save reports to DIR (default: terminal only)")
    p.add_argument("--min-score", dest="min_score", type=float, default=None, metavar="N",
                   help="Exit with code 1 if average score is below N (0-10). Used for pre-commit hooks.")
    p.add_argument("--agent", action="store_true",
                   help="Output structured Markdown action plan for AI coding agents (no ANSI, no HTML, no interactive questions)")
    return p


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "intent":
        from code_analyzer.intent_cli import run_intent_cli
        sys.exit(run_intent_cli(sys.argv[2:]))
    if len(sys.argv) >= 2 and sys.argv[1] == "health":
        from code_analyzer.health_cli import run_health_cli
        sys.exit(run_health_cli(sys.argv[2:]))
    if len(sys.argv) >= 2 and sys.argv[1] == "config":
        from code_analyzer.config_cli import run_config_cli
        sys.exit(run_config_cli(sys.argv[2:]))
    if len(sys.argv) >= 2 and sys.argv[1] == "agent":
        from code_analyzer.cli import _run_agent_review
        json_mode = "--json" in sys.argv
        sys.exit(_run_agent_review(sys.argv[2:], json_mode))
    parser = build_parser()
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
