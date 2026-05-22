"""Test Pain metrics (TP1-TP4) — analyzes test files to reveal hidden coupling.

Reads test files as a human signal of architecture quality:
- TP1: Real test coverage (not name-based inference)
- TP2: Mock density (mocks per test function → hidden coupling)
- TP3: Test complexity (complex tests → hard-to-test production code)
- TP4: Test isolation (DB/network deps in tests → integration-level coupling)
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

_EXTERNAL_DEPS = {"django", "requests", "httpx", "sqlite3", "psycopg2",
                  "redis", "celery", "boto3", "kafka", "pika", "aiopika"}
_MOCK_NAMES = {"patch", "MagicMock", "Mock", "monkeypatch", "AsyncMock",
               "patch.object", "patch.multiple", "create_autospec"}


def _is_test_file(path: Path) -> bool:
    return path.name.startswith("test_") and path.suffix == ".py"


def _find_test_file(filepath: str) -> Optional[Path]:
    """Find the corresponding test file for a source file.

    Looks for test_<name>.py in the same directory and in a tests/ subdirectory.
    """
    source = Path(filepath).resolve()
    stem = source.stem
    parent = source.parent

    candidates = [
        parent / f"test_{stem}.py",
        parent / "tests" / f"test_{stem}.py",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Also check if source is already a test file
    if _is_test_file(source):
        return source

    return None


def _count_source_symbols(source_file: Path) -> tuple:
    """Count functions and methods in a source file."""
    try:
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        _fix_parents(tree)
    except (SyntaxError, OSError):
        return (0, 0)

    funcs = 0
    methods = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        methods += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and node.parent and not isinstance(node.parent, ast.ClassDef):
                funcs += 1
    return (funcs, methods)


def _fix_parents(tree: ast.AST) -> None:
    """Set parent references on all nodes."""
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # type: ignore


def analyze_test_coverage(source_file: Path, test_file: Path) -> Dict[str, Any]:
    """TP1 — real test coverage by counting tested functions/methods.

    Matches test function names to source symbols by convention:
    test_<name> covers <name>.
    """
    funcs, methods = _count_source_symbols(source_file)
    total = funcs + methods
    if total == 0:
        return {"score": 100.0, "covered": 0, "total": 0}

    try:
        test_tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return {"score": 0.0, "covered": 0, "total": total}

    tested_names: set = set()
    for node in ast.walk(test_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name.startswith("test_"):
                tested_names.add(name[5:])  # strip "test_" prefix

    # Count source symbols matched by test names
    covered = 0
    try:
        source_tree = ast.parse(source_file.read_text(encoding="utf-8"))
        _fix_parents(source_tree)
    except (SyntaxError, OSError):
        return {"score": 0.0, "covered": 0, "total": total}

    for node in ast.walk(source_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and node.name in tested_names:
                covered += 1

    score = round((covered / total) * 100, 1) if total > 0 else 100.0
    return {"score": score, "covered": covered, "total": total}


def analyze_mock_density(test_file: Path) -> Dict[str, Any]:
    """TP2 — mock density: mocks per test function.

    Higher density = more hidden coupling in production code.
    """
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return {"score": 100.0, "mock_count": 0, "test_funcs": 0, "density": 0.0}

    _fix_parents(tree)

    mock_count = 0
    for node in ast.walk(tree):
        # Detect @patch decorators
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _MOCK_NAMES:
                mock_count += 1
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in _MOCK_NAMES:
                    mock_count += 1
                elif isinstance(node.func.value, ast.Name) and node.func.value.id in _MOCK_NAMES:
                    mock_count += 1
        # Detect with patch(...) context managers
        if isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    if isinstance(item.context_expr.func, ast.Name) and item.context_expr.func.id in _MOCK_NAMES:
                        mock_count += 1

    test_funcs = sum(
        1 for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    )
    density = round(mock_count / max(1, test_funcs), 2)
    score = round(max(0.0, 100.0 - density * 100), 1)
    return {"score": score, "mock_count": mock_count, "test_funcs": test_funcs, "density": density}


def analyze_test_complexity(test_file: Path) -> Dict[str, Any]:
    """TP3 — average cyclomatic complexity of test functions.

    Complex tests often signal hard-to-set-up production code.
    """
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return {"score": 100.0, "avg_complexity": 0.0, "test_funcs": 0}

    complexities = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            cx = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                       ast.With, ast.Assert, ast.comprehension)):
                    cx += 1
                elif isinstance(child, ast.BoolOp):
                    cx += len(child.values) - 1
            complexities.append(cx)

    avg = round(sum(complexities) / max(1, len(complexities)), 1)
    score = round(max(0.0, 100.0 - avg * 10), 1)
    return {"score": score, "avg_complexity": avg, "test_funcs": len(complexities)}


def analyze_test_isolation(test_file: Path) -> Dict[str, Any]:
    """TP4 — test isolation: detects DB/network dependencies in test imports.

    Tests importing django.db or requests are integration tests, not unit tests.
    This signals that production code is coupled to infrastructure.
    """
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return {"score": 100.0, "external_deps": []}

    external = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _EXTERNAL_DEPS:
                    external.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in _EXTERNAL_DEPS:
                    external.append(node.module)

    if not external:
        score = 100.0
    elif any("django.db" in d for d in external):
        score = 60.0
    elif any(d in _EXTERNAL_DEPS for d in external):
        score = 30.0
    else:
        score = 100.0

    return {"score": score, "external_deps": list(set(external))}


def analyze_test_pain(filepath: str) -> Dict[str, Any]:
    """Orchestrate all 4 test pain metrics and compute aggregate.

    Returns a dict with individual scores and aggregate (0-100).
    Returns default "no test file found" values if no corresponding test exists.
    """
    source_file = Path(filepath)
    test_file = _find_test_file(filepath)

    if test_file is None:
        return {
            "tp1": {"score": 0.0, "covered": 0, "total": 0},
            "tp2": {"score": 0.0, "mock_count": 0, "test_funcs": 0, "density": 0.0},
            "tp3": {"score": 0.0, "avg_complexity": 0.0, "test_funcs": 0},
            "tp4": {"score": 0.0, "external_deps": []},
            "aggregate": 0.0,
            "test_file": None,
        }

    tp1 = analyze_test_coverage(source_file, test_file)
    tp2 = analyze_mock_density(test_file)
    tp3 = analyze_test_complexity(test_file)
    tp4 = analyze_test_isolation(test_file)

    aggregate = round(
        tp1["score"] * 0.30 + tp2["score"] * 0.30 + tp3["score"] * 0.20 + tp4["score"] * 0.20,
        1,
    )

    return {
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "tp4": tp4,
        "aggregate": aggregate,
        "test_file": str(test_file),
    }
