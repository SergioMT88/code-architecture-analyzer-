# AGENTS.md — Code Architecture Analyzer v7.0.0

## Version History

| Version | Date | Key Features |
|---------|------|--------------|
| v7.0.0 | 2026-05-30 | Agent Review (metacognitive prompts, 20 design patterns, automatic agent integration) |
| v6.3.0 | 2026-05-24 | Agent mode (--agent produces structured Markdown for AI agents) |
| v6.2.0 | 2026-05-23 | UX overhaul (welcome, HTML dashboard, i18n pt/en) |
| v6.1.0 | 2026-05-24 | Intent Learning (learns from user feedback) |
| v6.0.0 | 2026-05-22 | Performance overhaul + Pylint removal (5-8x faster) |

## Entrypoints

- **CLI binary** (`npx code-architecture-analyzer your_file.py`): `bin/cli.js` (Node.js + commander, declared in `package.json` `bin` as `code-analyze`). Forwards to `bin/cli.py`.
- **Python thin shim** (`bin/cli.py`): inserts `src/` into `sys.path`, then calls `code_analyzer.cli:main`. All Python routes go through here.
- **Programmatic API** (`index.js`): exposes `analyze()`, `refactor()`, `validate()`.

## Commands

```
code-analyze <file.py>                     # analyze + refactor
code-analyze check <file.py>               # analyze only (no refactor)
code-analyze agent <file.py>               # generate metacognitive prompt for AI agent
code-analyze analyze <file.py> --dry-run   # preview changes
code-analyze analyze <file.py> --interactive
code-analyze refactor <file.py> [--dry-run]
code-analyze validate <file.py>            # syntax check
code-analyze init                          # create .analyzer.json
code-analyze info                          # system info
code-analyze setup                         # pip install ruff black isort pytest
code-analyze intent                        # manage Intent Learning (list/show/reset/export/import)
code-analyze health                        # detector health report
code-analyze config lang [pt|en]           # switch language
```

All commands support `--json` for machine-readable stdout.

## Package Layout

```
src/code_analyzer/
  __init__.py             # public API: analyze(), refactor(), validate()
  cli.py                  # dispatch() — subcommand router
  config.py               # DEFAULT_CONFIG, load_config, _parse_pyproject_toml
  constants.py            # centralized constants (weights, thresholds, confidence levels) [v7.0.0]
  orchestrator.py         # argparse entry point (build_parser + main)
  artifact_manager.py     # ArtifactRegistry
  validator.py            # CodeValidator, validate_file
  refactorer.py           # RefactoringOrchestrator, refactor_file
  report_generator.py     # ReportGenerator, generate_reports
  pipeline.py             # Pipeline core: _setup, _phase1-3, _finalize [v4.4]
  terminal_ui.py          # ScoreBundle, print functions [v4.4]
  interactive.py          # interactive_menu [v4.4]
  gate.py                 # check_min_score [v4.4]
  project_context.py      # load_project_context() — lê CLAUDE.md do projeto analisado [v3.2.2]
  pattern_advisor.py      # get_pattern_advice() — mapeia findings → Strategy/Facade/etc. [v3.3.0]
  pattern_analysis.py     # 20 design pattern detectors + quality checks + anti-patterns [v7.0.0]
  agent_review.py         # metacognitive prompt generator for AI coding agents [v7.0.0]
  agent_output.py         # generate_agent_json() for --agent mode [v6.3.0]
  history.py              # load_history(), save_history_snapshot(), get_last_matching_snapshot()
  i18n.py                 # internationalization (pt/en) [v6.2.0]
  limits.py               # centralized output limits
  analyzer/
    __init__.py           # run_analysis(), prune_criteria(), detect_all()
    core.py               # ArchitectureAnalyzer NodeVisitor; run_ruff() com ruleset expandido (substitui pylint em v6.0.0)
    context.py            # AnalysisContext dataclass
    scoring.py            # score_to_status, mi_grade, wrap_criterion, production_risk_score
    test_pain.py           # TP1-TP4: mock density, coverage, complexity, isolation [v5.0.0]
    detection_runner.py   # _autoload_detectors() + detect_all() [v3.4.0]
    detectors/
      __init__.py         # Finding dataclass, Detector ABC, REGISTRY list, @register
      srp.py … dataflow_extractor.py  # 51 files, one per criterion
bin/
  cli.js                  # Node.js wrapper with spinners/validation
  cli.py                  # thin shim (5 lines)
tests/
  test_skill_core.py      # 297 tests, imports from src/code_analyzer/
pyproject.toml            # installable package, pytest config, tool.code-analyzer config
CLAUDE.md                 # contexto do projeto para Claude Code
```

## Pipeline (src/code_analyzer/)

| Phase | Module | What it does |
|-------|--------|-------------|
| 1 Identification | `analyzer/core.py` (3 micro-phases) | AST scan + ruff (com ruleset PL substituindo pylint) |
| 2 Proposition | `report_generator.py` (2 micro-phases) | Scoring + action recommendations |
| 3 Implementation | `refactorer.py` (5 micro-phases) | Cleanup: docstring, dedup imports, rm unused imports, fix f-strings, rename ambiguous vars; then test scaffold, black/isort formatting, final validation |

`pipeline.py:run_pipeline()` drives the full pipeline via argparse. `cli.py:dispatch()` routes subcommands.

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
Test count: **311 tests**.

## Key constraints

- **v3.2.x only does safe cleanup**, not deep architectural refactoring (e.g., no God Class splitting). See `SKILL.md`.
- `dry-run` is always available; files are never modified without backup.
- Refactoring aborts if final syntax check fails; original file is preserved.
- The tool requires Python 3.8+ and Node.js 14+. Python dependencies (ruff, black, isort, pytest) are optional — install via `code-analyze setup` or `pip install`. Pylint removed in v6.0.0 — replaced by `ruff --select=E,F,W,B,SIM,UP,PL,RUF`.
- On Windows, `lib/python-utils.js:15-58` has extensive Python discovery logic.
- No pre-commit, no Makefile, no CI.

## Novidades v5.0.0 — Test Pain como Sinal de Arquitetura

| Feature | Módulo | O que faz |
|---------|--------|-----------|
| Test Pain metrics (TP1-TP4) | `analyzer/test_pain.py` | Analisa arquivos de teste: cobertura real, mock density, complexidade, isolamento |
| Mock density (TP2) | `analyzer/test_pain.py:analyze_mock_density()` | Conta `patch`/`MagicMock` por função de teste — revela acoplamento oculto |
| Production risk 5º componente | `analyzer/scoring.py:production_risk_score()` | Test pain agregado (0-100) alimenta o score de risco com peso 20% |
| Seção no relatório | `report_generator.py:_section_test_pain()` | Tabela com 4 sub-scores + aggregate no MD e HTML |

## Novidades v3.4.0 — Análise Estrutural

| Feature | Módulo | O que faz |
|---------|--------|-----------|
| Import fan-in (SC1) | `project_context.py:get_import_fan_in()` | Conta quantos .py do projeto importam este módulo |
| Git frequency (SC2) | `project_context.py:get_git_commit_count()` | `git log --follow` nos últimos 90 dias |
| Priority Index (SC3) | `project_context.py:compute_priority_index()` + `pipeline.py` | Combina fan-in + commits + cobertura em score 0-100 com label CRÍTICO/ALTA/MÉDIA/BAIXA |
| Cross-file dup (CF2) | `analyzer/semantic.py:compare_directory()` | Fingerprint AST normalizado em N arquivos |
| Project mode (CF1) | `cli.py: code-analyze project <dir>` | Varre todos .py do diretório e lista duplicações cross-file |
| Data-flow clusters (DF1-DF3) | `analyzer/dataflow.py` + `detectors/dataflow_extractor.py` | Grafo def-use em funções >50 linhas → sugere boundaries de extração com nome e range |

## Novidades v3.3.0 — Diagnóstico Inteligente

| Feature | Módulo | O que faz |
|---------|--------|-----------|
| StringDispatch detector | `detectors/string_dispatch.py` | Detecta `if self.X == "literal":` em ≥2 métodos da mesma classe → Finding com sugestão de Strategy Pattern |
| ROI diminishing returns | `history.py:check_roi_diminishing()` + `pipeline.py` | Se delta de score < 0.3 em 2+ execuções consecutivas, emite aviso no terminal com estratégias alternativas |
| Pattern Advisor | `pattern_advisor.py` + `report_generator.py` + `pipeline.py` | Lê findings e sugere padrões de design (Strategy, Facade, Template Method, DI) no terminal e no relatório MD |

## Limites conhecidos (v3.2.2)

| Limite | Impacto | Mitigação implantada |
|--------|---------|----------------------|
| ~~Pylint quebra em Django sem DJANGO_SETTINGS_MODULE~~ | Removido em v6.0.0 | Pylint substituido por `ruff --select=PL,...` que nao depende de configuracao de ambiente |
| Score mede convenção, não corretude | 9.28/10 com bugs críticos possível | Disclaimer em relatórios Markdown, HTML e terminal |
| Sem memória entre análises | Débitos do CLAUDE.md ignorados | `project_context.py` lê CLAUDE.md e exibe seção "Contexto do Projeto" |
| Cobertura inferencial | `test_X` cobre `X` por nome, não execução | Documentado como limitação; futuro: integrar `pytest --cov` |
| Bugs semânticos invisíveis | ORM incorreto, race conditions, lógica de negócio | Fora do escopo de análise estática |

## Style

- `pyproject.toml` sets `max-line-length = 100` via `[tool.ruff] line-length = 100`.
- All Python source code (docstrings, comments, internal messages) is in English. Terminal output visible to users stays in Portuguese.
- `SKILL.md` is the authoritative technical reference for the OpenCode skill definition.

## Architecture notes

- `lib/python-utils.js` bridges Node → Python via `spawn`. `runPythonScript` pipes stdio; `runPythonScriptWithJSON` captures stdout and parses JSON.
- Detector Registry pattern: 52 `@register` classes in `detectors/*.py`, auto-discovered via `detection_runner.py:_autoload_detectors()`. `detect_all(ctx)` replaces the 547-line `_evaluate_criteria()` God Method.
- `AnalysisContext` dataclass passes shared state to all detectors: `code`, `lines`, `filepath`, `classes`, `functions`, `imports`, `config`, `tree`.
- `artifact_manager.py` manages output directory creation, path helpers, artifact recording, and manifest saving.
- External tool (ruff) is invoked via subprocess and gracefully handles `FileNotFoundError`. Single-tool pipeline since v6.0.0.
- Design Patterns detection: `design_patterns.py` detects 8 patterns (Singleton, Factory, Strategy, Adapter, Repository, Observer, Facade, Template Method) via class name + method signature heuristics. Function-level Strategy selection also detected.
- `pattern_advisor.py` maps criteria findings to design pattern advice (Strategy, Facade, Observer, Template Method, Dependency Injection) in terminal and report.

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
