# ARCHBENCH v1.0

**Architecture Analysis Benchmark for Python**  
The first open benchmark for code architecture analyzer tools.

---

## What ARCHBENCH measures

ARCHBENCH evaluates how well a static analysis tool detects **architecture-level** problems — not just syntax errors or style violations. It covers 4 categories across 12 test cases:

| Category | Criteria | Test cases |
|----------|----------|-------------|
| **Security** | HardcodedSecrets, InjectionRisk (SQL + Command), MassAssignment | 2 recall + 1 precision |
| **SOLID** | LSP, DIP, SRP/GodClass, OCP, Cohesion | 3 recall + 1 precision |
| **Patterns** | StringDispatch, OrmInLoop/N+1, FeatureEnvy, ShotgunSurgery | 1 recall + project |
| **Anti-patterns** | LongFunction, UselessListComp, BareExcept | 1 recall + 1 precision |

## How it works

Each test case has a `ground_truth.json` declaring **what must be found** and **what must NOT be found**:

```json
{
  "command_injection.py": {
    "expected": {
      "InjectionRisk": {
        "line": 12,
        "confidence_min": 0.80,
        "description": "subprocess.run() shell=True + dynamic command"
      }
    },
    "must_not_find": []
  }
}
```

The runner executes `code-analyze check --stream --force` on each file, parses the NDJSON events, and computes:

| Metric | Formula |
|--------|---------|
| **Recall** | `hits / (hits + misses + expected_misses)` |
| **Precision** | `hits / (hits + false_positives)` |
| **F1** | `2 × (recall × precision) / (recall + precision)` |
| **Score** | F1 (0-100%) |

## v7.5.0 Results

### Single-file recall — 6/6 cases, 9/9 detectors

| Case | Detector | Expected | Found | Confidence | Score |
|------|----------|----------|-------|------------|-------|
| command_injection.py | InjectionRisk | 1 | 1 | 0.90 | **100%** |
| secrets_by_value.py | HardcodedSecrets | 3 | 3 | 0.95 | **100%** |
| lsp_violations.py | LSP | 2 | 2 | 0.75 | **100%** |
| mass_assignment_userinput.py | MassAssignment | 1 | 1 | 0.75 | **100%** |
| god_class_mixed.py | GodClass | 1 ⚠️ MISS | 0 | — | 0% |
| simple_gaps.py | LongFunction | 1 | 1 | 0.60 | 66.7% |
| simple_gaps.py | UselessListComp | 1 ⚠️ MISS | 0 | — | — |

### Single-file precision — 3/3 cases, 0 false positives

| Case | Expected | Findings | False Positives | Score |
|------|----------|----------|-----------------|-------|
| clean_service.py | 0 | 0 | 0 | **100%** |
| clean_abc.py | 0 | 1 (DesignPattern) | 0 | **100%** |
| benign_unpacking.py | 0 | 0 | 0 | **100%** |

### Project mode — complex_challenge

| Layer | Criteria | Expected | Found | Score |
|-------|----------|----------|-------|-------|
| Cross-file | ShotgunSurgery | 3 files | 3 | ✅ |
| Per-file | HardcodedSecrets | 2 | 2 | ✅ |
| Per-file | InjectionRisk | 3 | 3 | ✅ |
| Per-file | MassAssignment | 1 | 1 | ✅ |
| Per-file | StringDispatch | 1 | 1 | ✅ |
| Per-file | DIP | 1 | 1 | ✅ |
| Per-file | OrmInLoop | 1 | 2 | ✅ |
| Per-file | FeatureEnvy | 1 | 1 | ✅ |

**9/9 cross-file + per-file criteria detected. 38 total findings across 9 files.**

### Summary

| Metric | Score |
|--------|-------|
| Single-file recall | **85.2%** |
| Single-file precision | **100%** |
| Project mode | **100%** |
| **OVERALL** | **91.1% (A)** |

### Known gaps (documented in ground truth)

| Gap | Impact | Priority |
|-----|--------|----------|
| GodClass threshold = `max_methods + 5` misses 11-method cohesive-breaking classes | 0% on god_class_mixed.py | 🔴 High |
| No UselessListComp detector | misses `[x for x in xs]` anti-pattern | 🟡 Medium |

## Running the benchmark

```bash
# Run all test cases
python tests/archbench/runner.py --output results/results.json

# View summary
python -m json.tool results/results.json | grep -E "overall|grade|recall|precision"
```

## Contributing to ARCHBENCH

Other code architecture tools can adopt this benchmark. To add your tool:

1. Fork the repository
2. Add a new result file: `tests/archbench/results/<tool>-<version>.json`
3. Implement a runner that produces findings in ARCHBENCH format
4. Submit a PR with your results

### ARCHBENCH finding format

```json
{
  "event": "finding",
  "file": "path/to/file.py",
  "criterion": "DetectorName",
  "severity": "ALTA|MEDIA|BAIXA",
  "confidence": 0.0-1.0,
  "line": 42,
  "issue": "Description of the problem",
  "suggestion": "How to fix it",
  "location": "linha 42"
}
```

## Roadmap

- [ ] Add 50+ more test cases (target: 100% recall coverage)
- [ ] Add TaintFlow cross-module test cases
- [ ] Add CloneDetection cross-file test cases
- [ ] Add performance benchmark (analysis speed in files/sec)
- [ ] CI integration: run benchmark on every PR, fail if score regresses
- [ ] League table: compare tools on https://archbench.dev
