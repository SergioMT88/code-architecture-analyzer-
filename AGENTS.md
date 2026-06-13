# AGENTS.md — Integrating Code Architecture Analyzer with AI Agents

> Guide for AI coding agents (and the humans wiring them up) that drive
> `code-architecture-analyzer` programmatically. Agents are the **primary**
> consumer of this tool — every capability is reachable as machine-readable JSON.

## TL;DR for an agent

```bash
code-analyze manifest                  # 1. discover capabilities + known gaps (JSON)
code-analyze check <file.py> --agent   # 2. analyze one file → unified JSON envelope
code-analyze project <dir> --agent     # 2'. analyze a whole package → same envelope
```

1. Read `manifest` once to learn what the tool covers and — crucially — what it
   **does not** cover (`known_gaps`), so you know where to apply your own judgement.
2. Run `check --agent` (or `project --agent`) and parse the envelope below.
3. Apply `action_records` whose `risk_level` is `safe` and `confidence` is high;
   surface the rest to a human or reason about them yourself.
4. Re-run to confirm the score moved.

`--agent` writes **only** the JSON envelope to stdout — no banner, no spinner, no
footer. Safe to pipe straight into `json.load`.

## The envelope (schema 1.1)

`check <file> --agent` and `project <dir> --agent` emit the **same** top-level
shape, so an agent parses one contract regardless of input:

```jsonc
{
  "schema_version": "1.1",
  "mode": "file" | "project",
  "root": "<path>",
  "metacognitive_guide": "step-by-step reasoning instructions",
  "summary": {
    "files_analyzed": 1,
    "total_findings": 7,
    "critical": 2, "warnings": 3,
    "safe_auto_apply": 2,        // records you can apply without asking
    "cross_file_findings": 0
  },
  "files": { "<path>": { "score": 8.4, "grade": "B", "per_criterion": {…} } },
  "action_records": [
    {
      "id": "…", "file": "…", "criterion": "GodClass", "line": 42,
      "severity": "ALTA", "issue": "…", "suggestion": "…",
      "reasoning": "…", "impact": "…",
      "confidence": 0.9, "risk_level": "safe" | "review" | "risky",
      "verify": ["…"]            // how to check the change is correct
    }
  ],
  "semantic": {                  // NEW in 1.1 — informational, never affects score
    "taint_flows": [
      { "file": "…", "function": "execute", "type": "direct",
        "line": 6, "description": "USER_INPUT -> comando de shell executado",
        "confidence": 0.8 }
    ],
    "dataflow": { "clusters": 3 },
    "purity": { "pure": 4, "side_effect": 2, "unknown": 1 },
    "note": "informational - does not affect score"
  },
  "intent_learning": { "answers_recorded": 0, "noisy_detectors": [] }
}
```

### How an agent should use each block

- **`action_records`** — your work queue. Sort is already severity-then-confidence.
  - `risk_level == "safe"` **and** `confidence` high → apply automatically, then run `verify`.
  - otherwise → propose to the human, or reason using `reasoning` + `impact`.
- **`semantic`** — taint/dataflow/purity, **informational** (does not move the
  score). `taint_flows` is intra-file source→sink, **including class methods**.
  Treat a flow as a lead to investigate, not a confirmed vulnerability — validate
  whether the input is actually attacker-controlled and unsanitised.
- **`intent_learning.noisy_detectors`** — detectors the project marked as noisy;
  their findings carry penalty 0. Don't fight the project's own calibration.
- **`metacognitive_guide`** — prepend to your own reasoning before acting.

## Capabilities & honest gaps: `manifest`

```bash
code-analyze manifest        # JSON: features, schema, requirements, known_gaps
```

`known_gaps` is the contract for "what static analysis here cannot see." Each gap
has `agent_can_cover: true` and `guidance` telling you how to cover it. Current
high-value gaps an agent should pick up:

- **TaintFlow** — intra-file taint (incl. class methods) is built in since v7.6
  and lives under `semantic`; **cross-module** taint is still single-hop. Trace
  multi-hop import chains yourself.
- **BusinessLogic** — semantic analysis is limited to taint/dataflow/purity. ORM
  behavior, race conditions (TOCTOU), and business-rule correctness stay invisible.
- **ScoreCalibration** — the score measures *conventions* (SOLID, complexity,
  coupling), not correctness. A 9.9/10 file can still have critical bugs. Reweigh
  with security findings.

## CI gate: `--min-score`

```bash
code-analyze check <file> --min-score 8.0   # exit code 1 if avg score < 8.0
code-analyze project <dir> --min-score 8.0  # same, averaged across the package
```

Non-zero exit on failure — drop it into a pre-commit hook (`code-analyze init`
scaffolds one) or a CI step.

## Streaming progress: `--stream`

```bash
code-analyze check <file> --agent --stream
```

Emits NDJSON (one JSON object per line) during analysis: `phase` events, `gap`
events (the same `known_gaps`), then a final `summary`/`done`. Use when you want
incremental feedback instead of one blocking call.

## Full command surface (npm wrapper)

```
code-analyze <file.py>                    # analyze + refactor
code-analyze check <file.py>              # analyze only (no refactor)
code-analyze project <dir>                # cross-file analysis of a package
code-analyze project <dir> --threshold 0.9  # only the semantic-duplication scan
code-analyze dup <a.py> <b.py>            # semantic duplication between 2 files
code-analyze history <file.py>            # score history across runs
code-analyze refactor <file.py>           # refactor only
code-analyze validate <file.py>           # syntax check
code-analyze manifest                     # capabilities JSON (for agents)
code-analyze init                         # .analyzer.json + AGENTS.md + pre-commit
code-analyze intent / health              # Intent Learning management / detector health
code-analyze config lang [pt|en]          # switch terminal language
```

Shared flags on `analyze`/`check`/`project`: `--json`, `--agent`, `--stream`,
`--quiet`, `--compact`, `--min-score <n>`, `--force`, `--output <dir>`,
`--no-html`, `--no-cache`, `--no-tests`. On `analyze` also `--no-refactor`,
`--dry-run`, `--interactive`, `--patch-only`.

> `--no-refactor` is honored: with it, `analyze` never modifies the file. (Use
> `check` as the always-read-only shortcut.)

## Entrypoints (for contributors)

- **CLI** (`npx code-architecture-analyzer file.py` / `code-analyze`): `bin/cli.js`
  (Node + commander) → forwards to `bin/cli.py` → `code_analyzer.cli:main`.
- **Programmatic** (`index.js`): `analyze()`, `refactor()`, `validate()`.
- The engine is Python (`src/code_analyzer/`); the Node layer is a thin wrapper.

## Constraints

- Python 3.8+, Node 14+. Python deps (ruff, black, isort, pytest) are optional —
  the tool degrades gracefully and tells you what's missing.
- Files are never modified without a backup; refactoring aborts and restores the
  original if the final syntax check fails.
- All `--agent`/`--json` output is machine-clean on stdout; human/log noise goes
  to stderr.
