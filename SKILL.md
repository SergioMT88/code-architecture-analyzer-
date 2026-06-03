---
name: code-architecture-analyzer
description: "Analyzes a Python file or directory for architecture issues (SOLID, security, anti-patterns, N+1, cross-file) and automatically applies fixes. Runs code-analyze --agent, receives the metacognitive JSON contract, and acts on it without any manual copy-paste. 51 criteria, 358 tests."
compatibility: Python 3.8+
version: 7.3.1
---

# Code Architecture Analyzer — Agentic Loop

When this skill is invoked with a file or directory path, execute the full agentic loop below. Do not summarize and wait — drive the fixes autonomously.

## Step 1 — Run the analyzer

```bash
python src/code_analyzer/orchestrator.py "<path>" --agent
```

Capture the full JSON output. If the output is large, save it to a temp file and read it back.

## Step 2 — Read the metacognitive guide FIRST

The JSON contains a `metacognitive_guide` field at the top level. Read it completely before touching any code. It is your thinking protocol for this session.

The guide instructs you to:
1. Understand **why** each finding is a problem (read `reasoning`), not just what it is
2. Fix `severity: ALTA` records first (security/correctness), then MEDIA, then BAIXA
3. Prefer the `diff` field when present — it is a safe, mechanical transformation
4. Run `verify` steps after each fix, not in batch
5. Re-run the analyzer after all fixes to confirm the score improved
6. If a finding is wrong for this codebase, note it (Intent Learning) so it stops being surfaced

## Step 3 — Process action_records in priority order

Work through `action_records` sorted by severity (ALTA → MEDIA → BAIXA). For each record:

| Field | What to do with it |
|---|---|
| `reasoning` | Read it — understand the structural WHY before editing |
| `diff` | Apply directly if present (safe mechanical change) |
| `suggestion` | Apply if no diff is present |
| `verify` | Run the specified command or manual check after applying |
| `risk_level: safe` | Apply without asking |
| `risk_level: caution` | Apply but note the change |
| `risk_level: dangerous` | Show the proposed change and confirm before applying |

## Step 4 — Re-run and confirm

After all fixes:

```bash
python src/code_analyzer/orchestrator.py "<path>" --agent
```

Compare `summary.total_findings` and `summary.critical` to the original run. Report the delta.

## Step 5 — Handle Intent Learning

If any finding was skipped because it is intentional (not a real problem in this codebase), say so explicitly. The user can silence it permanently by answering the Intent Learning prompt on the next interactive run.

---

## Notes for callers

- **Single file:** `code-analyze file.py --agent`
- **Whole package:** `code-analyze src/mypackage/ --agent` (emits `mode: "project"` with per-file + cross-file records)
- **CI gate:** add `--min-score 7.0` to fail if score drops below threshold
- The `metacognitive_guide` is always in the JSON envelope — it is the contract between the tool and the agent
