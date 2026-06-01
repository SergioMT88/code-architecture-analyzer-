"""Accuracy harness — measures detector RECALL and PRECISION against a labeled corpus.

This is the project's north-star metric. Run it after any detector change:

    python scripts/measure_accuracy.py

Two corpora live under tests/corpus/:

  recall/    Files with PLANTED issues. Each issue is labeled with an inline
             comment  `# EXPECT: <CriterionName>`  on (or near) the offending
             line. Recall = labeled issues the tool actually found.

  precision/ Files of CLEAN, idiomatic code that SHOULD be silent. Any finding
             a detector raises here is a false positive (FP). Precision is
             reported as the FP count (lower is better; 0 is the goal).

Matching is criterion-name + line-window (±RECALL_LINE_WINDOW lines), so a
finding counts as a hit when the right detector fires near the labeled line.

Exit code is non-zero when recall drops below RECALL_TARGET or any FP exists,
so this can later gate commits.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from code_analyzer.analyzer import run_analysis  # noqa: E402

CORPUS = REPO_ROOT / "tests" / "corpus"
RECALL_DIR = CORPUS / "recall"
PRECISION_DIR = CORPUS / "precision"

RECALL_LINE_WINDOW = 3       # a finding within ±N lines of the label counts as a hit
RECALL_TARGET = 0.70         # gate threshold (informational for now)
CONFIDENCE_FLOOR = 0.0       # count every surfaced finding; raise to ignore low-conf

_EXPECT_RE = re.compile(r"#\s*EXPECT:\s*([A-Za-z_][A-Za-z0-9_]*)")
_LINE_RE = re.compile(r"linha\s+(\d+)")


def _finding_line(f: dict) -> int:
    """Extract the line number — structured `line` field if present, else parse
    it out of the Portuguese `location` string (e.g. 'linha 17')."""
    if f.get("line") is not None:
        return int(f["line"])
    m = _LINE_RE.search(str(f.get("location", "")))
    return int(m.group(1)) if m else 0


@dataclass
class Expectation:
    criterion: str
    line: int


@dataclass
class Detected:
    criterion: str
    line: int
    confidence: float
    penalty: float  # penalty_per_finding; 0 means informational (not a defect claim)


def _load_expectations(path: Path) -> List[Expectation]:
    out: List[Expectation] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = _EXPECT_RE.search(raw)
        if m:
            out.append(Expectation(criterion=m.group(1), line=i))
    return out


def _detected_findings(path: Path) -> List[Detected]:
    result = run_analysis(str(path))
    if not result.get("success"):
        raise RuntimeError(f"analysis failed for {path.name}: {result.get('error')}")
    out: List[Detected] = []
    for name, crit in result.get("criteria", {}).items():
        penalty = float(crit.get("penalty_per_finding", 2))
        for f in crit.get("findings", []):
            conf = float(f.get("confidence", 1.0))
            if conf < CONFIDENCE_FLOOR:
                continue
            out.append(Detected(
                criterion=name, line=_finding_line(f), confidence=conf, penalty=penalty,
            ))
    return out


def _measure_recall() -> Tuple[int, int, List[str]]:
    """Returns (hits, total, miss_descriptions)."""
    hits = 0
    total = 0
    misses: List[str] = []
    if not RECALL_DIR.exists():
        return (0, 0, [])
    for path in sorted(RECALL_DIR.glob("*.py")):
        expectations = _load_expectations(path)
        if not expectations:
            continue
        detected = _detected_findings(path)
        used: set = set()
        for exp in expectations:
            total += 1
            match_idx = None
            for idx, det in enumerate(detected):
                if idx in used:
                    continue
                if det.criterion == exp.criterion and abs(det.line - exp.line) <= RECALL_LINE_WINDOW:
                    match_idx = idx
                    break
            if match_idx is not None:
                used.add(match_idx)
                hits += 1
            else:
                misses.append(f"{path.name}:{exp.line}  MISS  {exp.criterion}")
    return (hits, total, misses)


def _measure_precision() -> Tuple[int, int, List[str]]:
    """Returns (clean_files, fp_count, fp_descriptions)."""
    fp_count = 0
    files = 0
    fps: List[str] = []
    if not PRECISION_DIR.exists():
        return (0, 0, [])
    for path in sorted(PRECISION_DIR.glob("*.py")):
        files += 1
        for det in _detected_findings(path):
            if det.penalty == 0:
                continue  # informational finding (e.g. DesignPatterns), not a defect claim
            fp_count += 1
            fps.append(f"{path.name}:{det.line}  FP  {det.criterion} (conf={det.confidence:.2f})")
    return (files, fp_count, fps)


def _clear_criteria_cache() -> None:
    """The criteria cache is keyed by content hash + version, so unchanged
    fixtures return stale results after a detector edit. Clear it so the
    harness always measures the CURRENT code, never a cached run."""
    import shutil
    cache = Path.home() / ".code-analyzer" / "criteria_cache"
    shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    print("=" * 64)
    print("  ACCURACY HARNESS — code-architecture-analyzer")
    print("=" * 64)
    _clear_criteria_cache()

    hits, total, misses = _measure_recall()
    recall = (hits / total) if total else 0.0
    print(f"\nRECALL    {hits}/{total} labeled issues found  =  {recall:.0%}")
    if misses:
        print("  misses:")
        for m in misses:
            print(f"    - {m}")

    files, fp_count, fps = _measure_precision()
    print(f"\nPRECISION {fp_count} false positives across {files} clean files")
    if fps:
        print("  false positives:")
        for f in fps:
            print(f"    - {f}")

    print("\n" + "-" * 64)
    ok_recall = recall >= RECALL_TARGET
    ok_precision = fp_count == 0
    print(f"  recall target {RECALL_TARGET:.0%}: {'PASS' if ok_recall else 'FAIL'}")
    print(f"  zero false positives: {'PASS' if ok_precision else 'FAIL'}")
    print("=" * 64)

    return 0 if (ok_recall and ok_precision) else 1


if __name__ == "__main__":
    raise SystemExit(main())
