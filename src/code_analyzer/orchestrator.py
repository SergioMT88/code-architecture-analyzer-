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
    p.add_argument("--html", action="store_true", help="Generate visual HTML dashboard")
    p.add_argument("--force", action="store_true", help="Forcar nova analise, ignorando o cache da Lazy Evaluation")
    p.add_argument("--patch-only", action="store_true", help="Gerar apenas arquivos .patch para revisao manual, sem modificar arquivos")
    p.add_argument("--output", dest="output_dir", default=None, metavar="DIR",
                   help="Save reports to DIR (default: terminal only)")
    p.add_argument("--min-score", dest="min_score", type=float, default=None, metavar="N",
                   help="Exit with code 1 if average score is below N (0-10). Used for pre-commit hooks.")
    return p


def main() -> None:
    parser = build_parser()
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
