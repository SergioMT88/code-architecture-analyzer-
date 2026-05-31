"""Test analyzer — evaluates testing practices on the file being analyzed.

Dimensions:
1. check_tests_passing()     — Are tests passing? (runs pytest)
2. check_test_coverage()     — Are functions adequately tested? (name mapping)
3. check_edge_cases()        — Are edge cases tested? (pattern heuristic)
4. check_test_type()         — Unit vs integration balance
5. check_nfr_tests()         — NFR tests (performance, etc.)
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _find_test_file(filepath: str, project_root: Optional[str] = None) -> Optional[Path]:
    """Find the test file corresponding to a source file.

    Searches for:
    - tests/test_<stem>.py
    - test_<stem>.py (same directory)
    - <stem>/tests/test_<stem>.py
    - Any test_*.py that imports the source module
    """
    src = Path(filepath)
    stem = src.stem
    search_roots = []

    if project_root:
        pr = Path(project_root)
    else:
        pr = src.parent
        # Walk up to find project root (has manage.py, pyproject.toml, etc.)
        for parent in [src.parent] + list(src.parent.parents)[:6]:
            if any((parent / f).exists() for f in ("manage.py", "pyproject.toml", "setup.py", "requirements.txt")):
                pr = parent
                break

    # Candidate paths
    candidates = [
        pr / "tests" / f"test_{stem}.py",
        pr / "test" / f"test_{stem}.py",
        src.parent / f"test_{stem}.py",
        pr / stem / "tests" / f"test_{stem}.py",
        pr / stem / "test_" f"{stem}.py",
    ]

    for c in candidates:
        if c.exists():
            return c

    # Fallback: scan for any test_*.py that imports this module
    module_name = stem
    for test_file in pr.rglob("test_*.py"):
        if test_file.name.startswith("__"):
            continue
        try:
            content = test_file.read_text(encoding="utf-8", errors="ignore")
            if module_name in content:
                return test_file
        except Exception:
            continue

    return None


def _find_all_test_files(project_root: Optional[str] = None) -> List[Path]:
    """Find all test files in the project."""
    if project_root:
        pr = Path(project_root)
    else:
        pr = Path.cwd()
    return list(pr.rglob("test_*.py"))


def _get_source_functions(filepath: str) -> List[str]:
    """Extract public function/method names from source file."""
    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
    except (SyntaxError, OSError):
        return []

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node.name)
    return functions


def _get_test_functions(test_filepath: str) -> List[str]:
    """Extract test function names from test file."""
    try:
        content = Path(test_filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
    except (SyntaxError, OSError):
        return []

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                functions.append(node.name)
    return functions


# ---------------------------------------------------------------------------
# Dimension 1: Are tests passing?
# ---------------------------------------------------------------------------

def check_tests_passing(filepath: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Run pytest on the test file and return results.

    Returns:
        {
            "status": "pass" | "fail" | "no_tests" | "error",
            "test_file": str | None,
            "passed": int,
            "failed": int,
            "errors": int,
            "skipped": int,
            "output": str,
            "score": int,  # 0-100
        }
    """
    test_file = _find_test_file(filepath, project_root)
    if test_file is None:
        return {
            "status": "no_tests",
            "test_file": None,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "output": "Nenhum arquivo de teste encontrado.",
            "score": 0,
        }

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "--tb=short", "--no-header", "-q"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
            cwd=str(test_file.parent.parent) if test_file.parent.name == "tests" else str(test_file.parent),
        )
        output = proc.stdout + proc.stderr

        # Parse output: "X passed, Y failed, Z errors, W skipped"
        passed = output.count(" passed")
        failed = output.count(" failed")
        errors = output.count(" error")
        skipped = output.count(" skipped")

        # More precise parsing
        import re
        pass_match = re.search(r"(\d+) passed", output)
        fail_match = re.search(r"(\d+) failed", output)
        err_match = re.search(r"(\d+) error", output)
        skip_match = re.search(r"(\d+) skipped", output)

        passed = int(pass_match.group(1)) if pass_match else 0
        failed = int(fail_match.group(1)) if fail_match else 0
        errors = int(err_match.group(1)) if err_match else 0
        skipped = int(skip_match.group(1)) if skip_match else 0

        total = passed + failed + errors
        if total == 0:
            status = "no_tests"
            score = 0
        elif failed == 0 and errors == 0:
            status = "pass"
            score = 100
        else:
            status = "fail"
            score = max(0, int((passed / max(1, total)) * 100))

        return {
            "status": status,
            "test_file": str(test_file),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "output": output[:2000],
            "score": score,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "test_file": str(test_file),
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
            "output": "Timeout: pytest demorou mais de 60 segundos.",
            "score": 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "test_file": str(test_file),
            "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
            "output": str(e),
            "score": 0,
        }


# ---------------------------------------------------------------------------
# Dimension 2: Are functions adequately tested?
# ---------------------------------------------------------------------------

def check_test_coverage(filepath: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Map source functions to test functions and compute coverage.

    Returns:
        {
            "source_functions": List[str],
            "tested_functions": List[str],
            "untested_functions": List[str],
            "coverage_pct": float,  # 0-100
            "score": int,  # 0-100
        }
    """
    source_funcs = _get_source_functions(filepath)
    test_file = _find_test_file(filepath, project_root)

    if test_file is None:
        return {
            "source_functions": source_funcs,
            "tested_functions": [],
            "untested_functions": source_funcs,
            "coverage_pct": 0.0,
            "score": 0,
        }

    test_funcs = _get_test_functions(str(test_file))

    # Map test_X → X
    tested = set()
    for tf in test_funcs:
        # Remove test_ prefix
        name = tf[5:] if tf.startswith("test_") else tf
        # Remove common suffixes
        for suffix in ("_success", "_error", "_empty", "_invalid", "_valid", "_none", "_true", "_false"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        tested.add(name)

    untested = [f for f in source_funcs if f not in tested]
    coverage_pct = (len(source_funcs) - len(untested)) / max(1, len(source_funcs)) * 100

    # Score: 100 if >80%, linear down to 0
    if coverage_pct >= 80:
        score = 100
    elif coverage_pct >= 50:
        score = 70
    elif coverage_pct >= 20:
        score = 40
    else:
        score = 10

    return {
        "source_functions": source_funcs,
        "tested_functions": list(tested),
        "untested_functions": untested,
        "coverage_pct": round(coverage_pct, 1),
        "score": score,
    }


# ---------------------------------------------------------------------------
# Dimension 3: Are edge cases tested?
# ---------------------------------------------------------------------------

_EDGE_CASE_PATTERNS = {
    "null": [r"assert.*is None", r"assert.*== None", r"assert.*is not None"],
    "empty": [r"assert len\(.*\) == 0", r"assert .+ == \[\]", r"assert .+ == \{\}", r'assert .+ == ""'],
    "error": [r"assertRaises", r"pytest\.raises", r"with pytest\.raises"],
    "boundary": [r"assert .+ > 0", r"assert .+ < 0", r"assert .+ >= 0", r"assert .+ <= 0",
                 r"assert .+ == 0", r"assert .+ == 1", r"assert .+ == -1"],
    "parametrize": [r"@pytest\.mark\.parametrize", r"@parameterized"],
    "type_error": [r"assertRaises\(TypeError\)", r"pytest\.raises\(TypeError\)"],
    "value_error": [r"assertRaises\(ValueError\)", r"pytest\.raises\(ValueError\)"],
    "unicode": [r"assert.*\\\\u", r'assert.*"\\\\u', r"emoji", r"accent"],
    "large_input": [r"range\(\d{4,}\)", r"list\(range\(\d{4,}\)\)"],
}


def check_edge_cases(filepath: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Analyze test file for edge case patterns.

    Returns:
        {
            "patterns_found": Dict[str, int],  # pattern_name -> count
            "total_patterns": int,
            "edge_case_score": int,  # 0-100
            "test_file": str | None,
        }
    """
    test_file = _find_test_file(filepath, project_root)
    if test_file is None:
        return {
            "patterns_found": {},
            "total_patterns": 0,
            "edge_case_score": 0,
            "test_file": None,
        }

    try:
        content = test_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {
            "patterns_found": {},
            "total_patterns": 0,
            "edge_case_score": 0,
            "test_file": str(test_file),
        }

    import re
    patterns_found = {}
    for name, regexes in _EDGE_CASE_PATTERNS.items():
        count = 0
        for rx in regexes:
            count += len(re.findall(rx, content))
        if count > 0:
            patterns_found[name] = count

    total = sum(patterns_found.values())

    # Score based on variety and count
    variety = len(patterns_found)
    if variety >= 5:
        score = 100
    elif variety >= 3:
        score = 70
    elif variety >= 1:
        score = 40
    else:
        score = 0

    return {
        "patterns_found": patterns_found,
        "total_patterns": total,
        "edge_case_score": score,
        "test_file": str(test_file),
    }


# ---------------------------------------------------------------------------
# Dimension 4: Unit vs Integration balance
# ---------------------------------------------------------------------------

_UNIT_MARKERS = {
    "django.test": "integration",
    "django.urls": "integration",
    "requests": "integration",
    "httpx": "integration",
    "pytest.fixture": "integration",
    "pytest.mark.django_db": "integration",
    "pytest.mark.selenium": "integration",
    "TestClient": "integration",
    "APIClient": "integration",
    "factory": "integration",
    "mock.patch": "unit",
    "unittest.mock": "unit",
    "MagicMock": "unit",
}


def check_test_type(filepath: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Classify tests as unit vs integration based on imports and patterns.

    Returns:
        {
            "unit_count": int,
            "integration_count": int,
            "balance": "good" | "skewed_unit" | "skewed_integration" | "no_tests",
            "details": List[str],
            "score": int,  # 0-100
        }
    """
    test_file = _find_test_file(filepath, project_root)
    if test_file is None:
        return {
            "unit_count": 0,
            "integration_count": 0,
            "balance": "no_tests",
            "details": [],
            "score": 0,
        }

    try:
        content = test_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {
            "unit_count": 0,
            "integration_count": 0,
            "balance": "no_tests",
            "details": [],
            "score": 0,
        }

    unit_count = 0
    integration_count = 0
    details = []

    for marker, test_type in _UNIT_MARKERS.items():
        occurrences = content.count(marker)
        if occurrences > 0:
            if test_type == "unit":
                unit_count += occurrences
            else:
                integration_count += occurrences
            details.append(f"{marker}: {occurrences}x ({test_type})")

    total = unit_count + integration_count
    if total == 0:
        balance = "no_tests"
        score = 50  # Neutral if no indicators found
    elif unit_count > 0 and integration_count == 0:
        balance = "skewed_unit"
        score = 60  # OK but might miss integration
    elif integration_count > 0 and unit_count == 0:
        balance = "skewed_integration"
        score = 50  # Might be slow
    else:
        balance = "good"
        score = 100

    return {
        "unit_count": unit_count,
        "integration_count": integration_count,
        "balance": balance,
        "details": details,
        "score": score,
    }


# ---------------------------------------------------------------------------
# Dimension 5: NFR tests (performance, etc.)
# ---------------------------------------------------------------------------

_NFR_PATTERNS = {
    "performance": [r"timeit", r"time\.time", r"perf_counter", r"monotonic"],
    "benchmark": [r"@pytest\.mark\.benchmark", r"pytest-benchmark", r"asv"],
    "load_test": [r"locust", r"k6", r"vegeta", r"wrk", r"ab "],
    "memory": [r"memory_profiler", r"tracemalloc", r"memory_profiler\.profile"],
    "security": [r"bandit", r"safety", r"pip-audit"],
}


def check_nfr_tests(filepath: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Check for NFR test patterns in test files and source.

    Returns:
        {
            "nfr_types_found": List[str],
            "has_performance_tests": bool,
            "has_load_tests": bool,
            "has_memory_tests": bool,
            "has_security_tests": bool,
            "score": int,  # 0-100
        }
    """
    import re

    all_files = [Path(filepath)]
    test_file = _find_test_file(filepath, project_root)
    if test_file:
        all_files.append(test_file)

    # Also check project root for load test files
    if project_root:
        pr = Path(project_root)
        for pattern in ["locustfile.py", "load_test.py", "bench_*.py", "perf_*.py"]:
            all_files.extend(pr.glob(pattern))

    nfr_types_found = []
    combined_content = ""
    for f in all_files:
        try:
            combined_content += f.read_text(encoding="utf-8", errors="ignore") + "\n"
        except OSError:
            continue

    for nfr_type, regexes in _NFR_PATTERNS.items():
        for rx in regexes:
            if re.search(rx, combined_content):
                nfr_types_found.append(nfr_type)
                break

    has_performance = "performance" in nfr_types_found or "benchmark" in nfr_types_found
    has_load = "load_test" in nfr_types_found
    has_memory = "memory" in nfr_types_found
    has_security = "security" in nfr_types_found

    # Score: having any NFR test is good
    found_count = len(nfr_types_found)
    if found_count >= 2:
        score = 100
    elif found_count == 1:
        score = 60
    else:
        score = 0

    return {
        "nfr_types_found": nfr_types_found,
        "has_performance_tests": has_performance,
        "has_load_tests": has_load,
        "has_memory_tests": has_memory,
        "has_security_tests": has_security,
        "score": score,
    }


# ---------------------------------------------------------------------------
# Aggregate: run all 5 dimensions
# ---------------------------------------------------------------------------

def analyze_testing_practices(filepath: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Run all 5 testing dimensions and return aggregate results.

    Returns:
        {
            "test_passing": {...},
            "test_coverage": {...},
            "edge_cases": {...},
            "test_type": {...},
            "nfr_tests": {...},
            "overall_score": int,  # 0-100
            "summary": str,
        }
    """
    tp = check_tests_passing(filepath, project_root)
    tc = check_test_coverage(filepath, project_root)
    ec = check_edge_cases(filepath, project_root)
    tt = check_test_type(filepath, project_root)
    nfr = check_nfr_tests(filepath, project_root)

    # Weighted average
    scores = [
        tp["score"] * 0.30,   # Test passing is most important
        tc["score"] * 0.25,   # Coverage
        ec["edge_case_score"] * 0.20,   # Edge cases
        tt["score"] * 0.15,   # Test type balance
        nfr["score"] * 0.10,  # NFRs
    ]
    overall = round(sum(scores))

    # Summary
    parts = []
    if tp["status"] == "pass":
        parts.append(f"{tp['passed']} testes passando")
    elif tp["status"] == "fail":
        parts.append(f"{tp['failed']} testes falhando")
    elif tp["status"] == "no_tests":
        parts.append("Nenhum teste encontrado")

    if tc["coverage_pct"] > 0:
        parts.append(f"{tc['coverage_pct']}% das funções testadas")

    if ec["total_patterns"] > 0:
        parts.append(f"{ec['total_patterns']} padrões de edge case")

    if tt["balance"] == "good":
        parts.append("Unit + Integração balanceados")
    elif tt["balance"] == "skewed_unit":
        parts.append("Apenas unitários")

    if nfr["nfr_types_found"]:
        parts.append(f"NFRs: {', '.join(nfr['nfr_types_found'])}")

    summary = " | ".join(parts) if parts else "Sem dados de teste"

    return {
        "test_passing": tp,
        "test_coverage": tc,
        "edge_cases": ec,
        "test_type": tt,
        "nfr_tests": nfr,
        "overall_score": overall,
        "summary": summary,
    }
