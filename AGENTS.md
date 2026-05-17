# AGENTS.md — Code Architecture Analyzer v2.1.3

## Entrypoints

- **CLI binary** (`npx code-architecture-analyzer your_file.py`): `bin/cli.py` (declared in `package.json` `bin` field as `code-analyze`).
- **Node.js CLI wrapper** (`bin/cli.js`): uses `commander` (richer flags: `--quiet`, `--json`, `--output`). Both CLIs shell out to Python scripts.
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

## Pipeline (scripts/)

| Phase | Script | What it does |
|-------|--------|-------------|
| 1 Identification | `scripts/analyzer.py` (3 micro-phases) | AST scan + pylint + ruff |
| 2 Proposition | `scripts/report_generator.py` (2 micro-phases) | Scoring + action recommendations |
| 3 Implementation | `scripts/refactorer.py` (5 micro-phases) | Cleanup: docstring, dedup imports, rm unused imports, fix f-strings, rename ambiguous vars; then test scaffold, black/isort formatting, final validation |

`scripts/orchestrator.py` drives the full pipeline. Python scripts find each other via `sys.path.insert(0, str(SCRIPTS))` in `bin/cli.py:16`.

## Config

`.analyzer.json` is searched: file's parent dir → file's grandparent dir → CWD. Example:

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
python -m unittest discover tests
python -m pytest tests/
python tests/test_skill_core.py
```

Tests use `unittest` with `tempfile.TemporaryDirectory` fixtures. No pytest config exists (no `pyproject.toml`). No CI pipeline.

## Key constraints

- **v2.1.3 only does safe cleanup**, not deep architectural refactoring (e.g., no God Class splitting). See `SKILL.md:76`.
- `dry-run` is always available; files are never modified without backup.
- Refactoring aborts if final syntax check fails; original file is preserved.
- The tool requires Python 3.8+ and Node.js 14+. Python dependencies (pylint, ruff, black, isort, pytest) are optional — install via `code-analyze setup` or `pip install`.
- On Windows, `lib/python-utils.js:15-58` has extensive Python discovery logic (checks `py -3`, `PYTHON` env, common paths).
- No pre-commit, no Makefile, no CI.

## Style

- `.flake8` sets `max-line-length = 100`.
- Code is bilingual (JS/Python). Python scripts are NOT a pip-installable package (no `setup.py`/`pyproject.toml`).
- `SKILL.md` is the authoritative technical reference for the OpenCode skill definition.

## Architecture notes

- `lib/python-utils.js` bridges Node → Python via `spawn`. `runPythonScript` pipes stdio; `runPythonScriptWithJSON` captures stdout and parses JSON.
- `scripts/artifact_manager.py` manages output directory creation, path helpers, artifact recording, and manifest saving.
- `scripts/analyzer.py:1084` runs 10 evaluation criteria (SRP, GodClass, Coupling, DIP, Cohesion, OCP, LayerSeparation, DesignPatterns, CircularDeps, InterfaceSegregation). Each of these. If a criterion is in `config.ignore_criteria`, it is skipped.
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
- Cada novo critério no `analyzer.py` precisa de `ignore_criteria` suporte + teste
- Rodar `python -m pytest tests/` antes de marcar como concluído

## Roadmap / docs/

Local project planning files live in `docs/` (gitignored, not published to npm):
- `docs/backlog.md` — full product backlog including **P3 LLM Error Detection** items
- `docs/sprint_atual.md` — current sprint scope and tasks
- `docs/sprint_concluida/` — archived sprints
- `docs/uso.md` — usage guide

**LLM Error Detection** is a new P3 priority: add static-analysis criteria for patterns LLMs commonly generate (bare `except:`, mutable defaults, shadowing builtins, `== None`, print leaks, async/sync mismatch, unused variables). See `docs/backlog.md` for full list. Each new criterion needs a test in `tests/test_skill_core.py`.
