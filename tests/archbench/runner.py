"""ARCHBENCH v1.0 — Architecture Analysis Benchmark runner.

Usage: python tests/archbench/runner.py [--output results/v7.5.0.json]

Runs code-architecture-analyzer against each corpus test case and computes
recall, precision, and F1 per criterion. Results are saved as JSON.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_PATH = Path(__file__).resolve().parent / "ground_truth.json"
CLI_ENTRY = str(PROJECT_ROOT / "src" / "code_analyzer" / "cli.py")


def load_ground_truth() -> Dict[str, Any]:
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


def run_analysis(filepath: str) -> List[Dict[str, Any]]:
    args = [
        sys.executable, CLI_ENTRY, "check", filepath,
        "--stream", "--force",
    ]
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return []

    findings: List[Dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or '"event": "finding"' not in line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return findings


def run_project_analysis(root_path: str) -> List[Dict[str, Any]]:
    args = [
        sys.executable, CLI_ENTRY, "check", root_path,
        "--stream", "--force",
    ]
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return []

    findings: List[Dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or '"event": "finding"' not in line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return findings


def evaluate_single_file(
    case_name: str, case: Dict[str, Any],
) -> Dict[str, Any]:
    filepath = str(PROJECT_ROOT / case["file"])
    is_decoy = case.get("is_decoy", False)
    expected = case.get("expected", {})
    must_not = case.get("must_not_find", [])

    findings = run_analysis(filepath)

    result: Dict[str, Any] = {
        "case": case_name,
        "file": case["file"],
        "is_decoy": is_decoy,
        "total_findings": len(findings),
        "detectors_hit": {},
        "detectors_missed": {},
        "detectors_expected_miss": {},
        "false_positives": [],
    }

    if is_decoy:
        for f in findings:
            crit = f.get("criterion", "?")
            sev = f.get("severity", "?")
            if crit not in ("RuffFormat", "DesignPatterns", "PrintLeak"):
                result["false_positives"].append({
                    "criterion": crit,
                    "severity": sev,
                    "line": f.get("line", 0),
                    "issue": f.get("issue", "")[:100],
                })
        result["score"] = 100 if not result["false_positives"] else max(0, 100 - len(result["false_positives"]) * 15)
        return result

    for crit_name, crit_expected in expected.items():
        if crit_expected.get("expected") == "MISS":
            result["detectors_expected_miss"][crit_name] = crit_expected
            continue

        found = [f for f in findings if f.get("criterion") == crit_name]
        expected_count = crit_expected.get("count", 1)
        found_count = len(found)
        min_conf = crit_expected.get("confidence_min", 0.0)
        high_conf_found = [f for f in found if f.get("confidence", 0) >= min_conf]

        if found_count >= expected_count and high_conf_found:
            result["detectors_hit"][crit_name] = {
                "expected": expected_count,
                "found": found_count,
                "confidence_ok": len(high_conf_found),
                "confidence_min": min_conf,
            }
        else:
            result["detectors_missed"][crit_name] = {
                "expected": expected_count,
                "found": found_count,
                "confidence_ok": len(high_conf_found) if found else 0,
                "confidence_min": min_conf,
                "reason": crit_expected.get("description", ""),
            }

    for f in findings:
        crit = f.get("criterion", "?")
        if crit not in expected and crit not in ("RuffFormat", "DesignPatterns", "PrintLeak"):
            if crit in must_not:
                result["false_positives"].append({
                    "criterion": crit,
                    "severity": f.get("severity", "?"),
                    "line": f.get("line", 0),
                    "issue": f.get("issue", "")[:100],
                })

    hit = len(result["detectors_hit"])
    missed = len(result["detectors_missed"])
    expected_miss = len(result["detectors_expected_miss"])
    total_expected = hit + missed + expected_miss
    weight_fp = len(result["false_positives"])

    result["recall"] = round(hit / max(total_expected, 1) * 100, 1)
    result["precision"] = round(hit / max(hit + weight_fp, 1) * 100, 1)
    result["f1"] = round(
        2 * (result["recall"] * result["precision"]) / max(result["recall"] + result["precision"], 1), 1
    )
    result["score"] = round(result["f1"], 1)

    return result


def evaluate_project(case_name: str, case: Dict[str, Any]) -> Dict[str, Any]:
    root_path = case["root"]
    if not Path(root_path).is_absolute():
        root_path = str(PROJECT_ROOT / root_path)

    expected_cross = case.get("expected_cross_file", {})
    expected_per = case.get("expected_per_file", {})

    findings = run_project_analysis(root_path)

    result: Dict[str, Any] = {
        "case": case_name,
        "root": case["root"],
        "total_findings": len(findings),
        "cross_file": {},
        "per_file": {},
        "score": 0,
    }

    for crit_name, crit_expected in expected_cross.items():
        found = [f for f in findings if f.get("criterion") == crit_name]
        expected_count = crit_expected.get("count", 1)
        result["cross_file"][crit_name] = {
            "expected": expected_count,
            "found": len(found),
            "ok": len(found) >= expected_count,
        }

    for file_name, file_criteria in expected_per.items():
        file_matches = [f for f in findings if f.get("file") == file_name]
        result["per_file"][file_name] = {}
        for crit_name, _ in file_criteria.items():
            found = [f for f in file_matches if f.get("criterion") == crit_name]
            result["per_file"][file_name][crit_name] = {
                "found": len(found),
                "ok": len(found) > 0,
            }

    cross_ok = sum(1 for c in result["cross_file"].values() if c["ok"])
    cross_total = len(result["cross_file"])
    per_ok = sum(
        1 for fc in result["per_file"].values()
        for c in fc.values() if c["ok"]
    )
    per_total = sum(len(fc) for fc in result["per_file"].values())

    total_ok = cross_ok + per_ok
    total_possible = cross_total + per_total
    result["score"] = round(total_ok / max(total_possible, 1) * 100, 1) if total_possible > 0 else 100

    return result


def run_benchmark(output_path: Optional[str] = None) -> Dict[str, Any]:
    gt = load_ground_truth()
    started = time.time()

    results: Dict[str, Any] = {
        "benchmark": "ARCHBENCH v1.0",
        "tool": "code-architecture-analyzer",
        "version": "7.5.0",
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": 0,
        "single_file": [],
        "project": [],
        "summary": {},
    }

    for case_name, case in gt["cases"].get("single_file", {}).items():
        result = evaluate_single_file(case_name, case)
        results["single_file"].append(result)
        status = (
            "PASS" if result["score"] >= 80
            else "WARN" if result["score"] >= 50
            else "FAIL"
        )
        print(f"  {case_name:30s}  {result['score']:5.1f}%  {status}")

    for case_name, case in gt["cases"].get("project", {}).items():
        result = evaluate_project(case_name, case)
        results["project"].append(result)
        status = "PASS" if result["score"] >= 80 else "WARN" if result["score"] >= 50 else "FAIL"
        print(f"  {case_name:30s}  {result['score']:5.1f}%  {status}")

    sf_scores = [r["score"] for r in results["single_file"]]
    pj_scores = [r["score"] for r in results["project"]]

    sf_avg = sum(sf_scores) / len(sf_scores) if sf_scores else 0
    pj_avg = sum(pj_scores) / len(pj_scores) if pj_scores else 0
    overall = round((sf_avg * 0.6 + pj_avg * 0.4), 1)

    results["summary"] = {
        "single_file_avg": round(sf_avg, 1),
        "project_avg": round(pj_avg, 1),
        "overall_score": overall,
        "grade": (
            "A" if overall >= 90 else "B" if overall >= 80
            else "C" if overall >= 70 else "D" if overall >= 60 else "F"
        ),
    }

    results["duration_seconds"] = round(time.time() - started, 1)

    print(f"\n  {'Single-file avg':30s}  {sf_avg:5.1f}%")
    print(f"  {'Project avg':30s}  {pj_avg:5.1f}%")
    print(f"  {'OVERALL':30s}  {overall:5.1f}%  ({results['summary']['grade']})")

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Results saved to {output_path}")

    return results


if __name__ == "__main__":
    output = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--output" else None
    run_benchmark(output or "tests/archbench/results/v7.5.0.json")
