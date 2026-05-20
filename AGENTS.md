# AGENTS.md — Code Architecture Analyzer v3.2.0

## Entrypoints

- **CLI binary** (`npx code-architecture-analyzer your_file.py`): `bin/cli.js` (Node.js + commander, declared in `package.json` `bin` as `code-analyze`). Forwards to `bin/cli.py`.
- **Python thin shim** (`bin/cli.py`): inserts `src/` into `sys.path`, then calls `code_analyzer.cli:main`. All Python routes go through here.
- **Programmatic API** (`index.js`): exposes `analyze()`, `refactor()`, `validate()`.

## Commands

```
code-analyze <file.py>                     # analyze + refactor
code-analyze check <file.py>               # analyze only (no refactor)
code-analyze analyze <file.py> --dry-run   # preview changes
code-analyze analyze <file.py> --interactive
code-analyze refactor <file.py> [--dry-run]
code-analyze validate <file.py>            # syntax check
code-analyze init                          # create .analyzer.json
code-analyze info                          # system info
code-analyze setup                         # pip install pylint ruff black isort pytest
```

All commands support `--json` for machine-readable stdout.

## Package Layout

```
src/code_analyzer/
  __init__.py             # public API: analyze(), refactor(), validate()
  cli.py                  # dispatch() — subcommand router
  config.py               # DEFAULT_CONFIG, load_config, _parse_pyproject_toml
  orchestrator.py         # argparse pipeline (build_parser + run_pipeline + main)
  artifact_manager.py     # ArtifactRegistry
  validator.py            # CodeValidator, validate_file
  refactorer.py           # RefactoringOrchestrator, refactor_file
  report_generator.py     # ReportGenerator, generate_reports
  analyzer/
    __init__.py           # run_analysis(), prune_criteria(), detect_all()
    core.py               # ArchitectureAnalyzer NodeVisitor (~300 lines)
    context.py            # AnalysisContext dataclass
    scoring.py            # score_to_status, mi_grade, wrap_criterion
    detectors/
      __init__.py         # Finding dataclass, Detector ABC, REGISTRY list, @register
      srp.py … abstract_method.py  # 34 files, one per criterion
bin/
  cli.js                  # Node.js wrapper with spinners/validation
  cli.py                  # thin shim (5 lines)
tests/
  test_skill_core.py      # 80 tests, imports from src/code_analyzer/
pyproject.toml            # installable package, pytest config, tool.code-analyzer config
```

## Pipeline (src/code_analyzer/)

| Phase | Module | What it does |
|-------|--------|-------------|
| 1 Identification | `analyzer/core.py` (3 micro-phases) | AST scan + pylint + ruff |
| 2 Proposition | `report_generator.py` (2 micro-phases) | Scoring + action recommendations |
| 3 Implementation | `refactorer.py` (5 micro-phases) | Cleanup: docstring, dedup imports, rm unused imports, fix f-strings, rename ambiguous vars; then test scaffold, black/isort formatting, final validation |

`orchestrator.py:run_pipeline()` drives the full pipeline via argparse. `cli.py:dispatch()` routes subcommands.

## Config

`.analyzer.json` is searched: file's parent dir → grandparent dir → CWD. Also supported via `pyproject.toml [tool.code-analyzer]`. Example:

```json
{"max_methods_per_class": 10, "max_lines_per_class": 200, ...}
```

## Outputs

```
.skill_outputs/<filename>/<timestamp>/
  analysis/<file>_analysis.json
  reports/<file>_report.md
  refactors/<file>_diff.txt
  backups/<file>_backup.py
  tests/test_<file>.py       # pytest scaffold (skipped if exists)
  logs/execution_manifest.json
```

`.skill_outputs/` is gitignored.

## Testing

```
pip install -e .             # install in editable mode (enables pytest pythonpath)
python -m pytest tests/ -v   # runs all 80 tests
python tests/test_skill_core.py  # direct execution also works
```

Tests use `unittest` with `tempfile.TemporaryDirectory` fixtures. `pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["src"]`.

## Key constraints

- **v2.1.5 only does safe cleanup**, not deep architectural refactoring (e.g., no God Class splitting). See `SKILL.md`.
- `dry-run` is always available; files are never modified without backup.
- Refactoring aborts if final syntax check fails; original file is preserved.
- The tool requires Python 3.8+ and Node.js 14+. Python dependencies (pylint, ruff, black, isort, pytest) are optional — install via `code-analyze setup` or `pip install`.
- On Windows, `lib/python-utils.js:15-58` has extensive Python discovery logic.
- No pre-commit, no Makefile, no CI.

## Style

- `pyproject.toml` sets `max-line-length = 100` via `[tool.ruff] line-length = 100`.
- All Python source code (docstrings, comments, internal messages) is in English. Terminal output visible to users stays in Portuguese.
- `SKILL.md` is the authoritative technical reference for the OpenCode skill definition.

## Architecture notes

- `lib/python-utils.js` bridges Node → Python via `spawn`. `runPythonScript` pipes stdio; `runPythonScriptWithJSON` captures stdout and parses JSON.
- Detector Registry pattern: 34 `@register` classes in `detectors/*.py`, auto-discovered via explicit imports in `analyzer/__init__.py`. `detect_all(ctx)` replaces the 547-line `_evaluate_criteria()` God Method.
- `AnalysisContext` dataclass passes shared state to all detectors: `code`, `lines`, `filepath`, `classes`, `functions`, `imports`, `config`, `tree`.
- `artifact_manager.py` manages output directory creation, path helpers, artifact recording, and manifest saving.
- External tools (ruff + pylint) are invoked via subprocess and gracefully handle `FileNotFoundError`.

## Workflow: item → código

Cada melhoria segue este fluxo:

```
docs/backlog.md  →  docs/sprint_atual.md  →  código + testes  →  docs/sprint_concluida/
     │                  │                         │                    │
     └── item ⬜        └── puxa item              └── implementa       └── arquiva
         marca ✅                                  └── pytest passando
```

Regras:
- Só mover para `sprint_concluida/` quando o item tem **teste passando + smoke test OK**
- Cada item vira um arquivo `YYYY-MM-DD-itemN-desc.md` em `sprint_concluida/`
- Cada novo critério em `detectors/` precisa de `ignore_criteria` suporte + teste em `test_skill_core.py`
- Rodar `python -m pytest tests/` antes de marcar como concluído

## Roadmap / docs/

Local project planning files live in `docs/` (gitignored, not published to npm):
- `docs/backlog.md` — full product backlog
- `docs/sprint_atual.md` — current sprint scope and tasks
- `docs/sprint_concluida/` — archived sprints
- `docs/uso.md` — usage guide
