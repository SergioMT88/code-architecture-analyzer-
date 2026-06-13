# Changelog

## [7.6.0] — 2026-06-13

Visible semantic analysis + complete agent interface. Two user feedbacks drove
this release: (1) "the tool only does static analysis, no semantics" — the
capability existed (taint/dataflow/purity) but was invisible; (2) coding agents
couldn't extract everything from the engine through the npm wrapper.

### Added
- **Single-file taint** (`analyze_file_taint`): walks the whole AST with
  `ast.walk`, so it analyses **class methods** too — which the cross-module pass
  (`detect_taint_flows`, top-level only) never covered. Informational (penalty 0,
  never affects the score); respects `ignore_criteria: ["TaintFlow"]`; caps at 25
  findings, skips files over 20k lines.
- **`semantic` block in the agent envelope** (taint_flows + dataflow clusters +
  purity counts), surfaced in the terminal (absence is visible too), in the
  Markdown report (`## Análise Semântica`), and — for projects — aggregated and
  deduplicated by (file, line).
- **AGENT_SCHEMA_VERSION 1.0 → 1.1** (additive: new top-level `semantic` key).
- npm wrapper commands that previously only existed in the Python engine: `dup`,
  `history`, `project` (dual backend: `--threshold` runs the duplication scan,
  otherwise the full cross-file pipeline).
- npm wrapper now forwards `--compact`, `--min-score`, `--patch-only`,
  `--no-cache`, `--no-tests`, `--no-html`.
- `AGENTS.md` rewritten as a public agent-integration guide and shipped in the
  npm package (`files`).
- `scripts/npm_smoke.sh`: 7-step wrapper⇄engine contract test, wired into CI.

### Fixed
- **`--no-refactor` was silently dropped by the wrapper** (Commander turns it
  into `options.refactor === false`, not `options.noRefactor`) — the tool
  **refactored when the agent asked for analysis only**. Now honored.
- **`--agent` emitted polluted stdout**: header/spinner/footer leaked into the
  JSON envelope, breaking `json.load`. Introduced `cleanMode` (json|stream|agent)
  to suppress all decoration.
- `--html` in the wrapper forwarded a positive flag the engine no longer has
  (HTML is automatic since v6.2), crashing argparse with exit 2. Now only
  `--no-html`.
- `project --json` crashed with "Object of type set is not JSON serializable"
  (`known_project_modules` was a set in `result["config"]`). Now a sorted list.
- Taint no longer treats `sys.stdout`/`sys.stderr.write` as a file-write sink
  (FP caught by self-testing the tool on its own code).
- `--agent` description corrected (it has been a JSON envelope since v7.0, not
  Markdown).

### Changed
- `known_gaps` (manifest + stream) are honest again: TaintFlow now states
  intra-file taint incl. class methods is built in; BusinessLogic states semantic
  analysis is limited to taint/dataflow/purity.

### Internal
- Test count: 404 (0 failures), 0 ruff errors. Accuracy harness: 13/13 recall, 0 FP.

## [7.5.0] — 2026-06-08

### Added
- B10: Taint Flow cross-module detection (6 source types, 5 sink types, intra + cross-module)
- B11: Pattern×Suggestion cross-file advisor (ShotgunSurgery→Facade, HighFanIn→DI, Clone→Template, Taint→Sanitization, GodClass→Strategy)
- B+: GodClass cross-file detection via symbol imports (threshold 10, severity MEDIA, confidence 0.7)
- CI/CD: GitHub Actions workflow (test matrix Python 3.8-3.12 + lint + smoke test)
- pytest-cov integration with coverage reporting

### Changed
- ReportGenerator split into `reporting/` submodule — from 41 methods / 1039 lines to 12 methods / 291 lines
- Broad `except Exception` reduced from 77 → 14 documented instances
- Version synchronized across pyproject.toml and package.json (7.5.0)
- Fixed `patterns/` directory inclusion in npm package

### Fixed
- 132 ruff errors resolved (F401 unused imports, E402 import ordering, F841 unused variables, E741 ambiguous names, F821 undefined names, F541 f-string placeholders)
- Circular import resolved via `_version.py` extraction
- 21 GoF pattern detector files missing from npm package

### Internal
- Project index now integrates taint flow + god class cross-file detectors
- Project pipeline prints pattern suggestions section
- Test count: 385 (0 failures)

## [7.4.1] — 2026-05-30

### Added
- B9a: Cross-file clone detection via AST-normalized fingerprints
- Stripe key detection by name pattern (to avoid GitHub secret scanning)

## [7.4.0] — 2026-05-24

### Added
- B9c: Cross-module symbol graph + HighFanIn detector
- blast_radius filled from symbol index in agent JSON output

## [7.3.1] — 2026-05-23

### Fixed
- ImportExists false positive for internal package modules in project mode

## [7.3.0] — 2026-05-22

### Added
- Unified `--agent` JSON contract for file and directory modes
- Metacognitive guide, mechanical diffs, Intent Learning integrated into agent output

## [7.2.1] — 2026-05-21

### Fixed
- `--agent` mode unified into single JSON schema for file + directory

## [7.2.0] — 2026-05-20

### Added
- Cross-file analysis foundation: directory input + literal Shotgun Surgery

## [7.0.0] — 2026-05-16

### Added
- Agent Review v2: metacognitive prompts with 20 design patterns
- Design pattern quality checks and anti-pattern detection
- `agent` subcommand with `--json` output

## [6.4.0] — 2026-05-14

### Added
- Agent Review: metacognitive prompt generator for AI coding agents

## [6.3.0] — 2026-05-12

### Added
- Agent mode (`--agent` flag) producing structured Markdown output

## [6.2.0] — 2026-05-10

### Added
- UX overhaul: welcome screen, HTML dashboard, i18n pt/en

## [6.1.0] — 2026-05-08

### Added
- Intent Learning: learns from user feedback to silence non-issues

## [6.0.0] — 2026-05-06

### Changed
- Pylint removed — replaced by ruff with expanded rule set
- 5-8x performance improvement

## [5.0.0] — 2026-05-04

### Added
- Test Pain metrics: mock density (TP2), coverage, complexity, isolation (TP1-TP4)
- Production risk score includes test pain (weight 20%)

## [4.4.0] — 2026-05-02

### Added
- Terminal UI overhaul: ScoreBundle, print functions
- Interactive menu for refactoring
- Min-score gate for CI/CD integration

## [3.4.0] — 2026-04-28

### Added
- Import fan-in (SC1), Git frequency (SC2), Priority Index (SC3)
- Cross-file duplication detection (CF2) via AST fingerprint
- Project mode (`code-analyze project <dir>`)
- Data-flow clusters (DF1-DF3) for function extraction boundaries

## [3.3.0] — 2026-04-25

### Added
- StringDispatch detector → Strategy Pattern suggestion
- ROI diminishing returns warning
- Pattern Advisor: maps findings → design patterns (Strategy, Facade, Template Method, DI)

## [3.2.2] — 2026-04-22

### Added
- Project context reading from CLAUDE.md
- Coverage inference by file name (test_X covers X)

## [3.0.0] — 2026-04-18

### Added
- 51 architecture criteria (SOLID, anti-patterns, security, Django-aware)
- Detector Registry pattern with auto-discovery
- AnalysisContext dataclass for shared state

## [2.0.0] — 2026-04-10

### Added
- Pipeline 3 phases: Identification → Proposition → Implementation
- Refactoring engine: 5 micro-phases with dry-run support
- Artifact manager with backup/manifest

## [1.0.0] — 2026-04-01

### Added
- Initial release: AST-based Python architecture analysis
- Code scoring (0-10) with maintainability index
- Safe refactoring with automatic backup
- CLI with `analyze`, `check`, `refactor`, `validate` commands
