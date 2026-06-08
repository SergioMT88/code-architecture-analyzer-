"""Diff generation for 4 mechanical patterns.

Generates suggested code transformations (diffs) for common patterns:
1. dict[k] → dict.get(k) + raise ValueError
2. == None → is None
3. range(len()) → enumerate()
4. except: → except Exception:
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List


@dataclass
class SuggestedDiff:
    """A suggested code transformation."""
    pattern: str
    location: str
    line: int
    confidence: float
    before: str
    after: str
    explanation: str
    risk_level: str = "safe"  # safe, moderate, risky


def detect_dict_subscript(tree: ast.AST, code: str, lines: List[str]) -> List[SuggestedDiff]:
    """Detect dict[key] and suggest dict.get(key).

    Pattern: payload["user_id"] → payload.get("user_id")
    Only triggers when the dict comes from an external source (json.loads, .json(), request.data, etc.)
    Skips assignments (dict[key] = value).
    """
    diffs = []
    external_sources = {"json", "loads", "load", "json", "request", "data", "body", "form", "args", "headers"}

    # Collect all subscript targets (left side of assignments)
    assignment_targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    assignment_targets.add(id(target))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        if id(node) in assignment_targets:
            continue  # Skip assignments
        if not isinstance(node.slice, ast.Constant) or not isinstance(node.slice.value, str):
            continue

        # Check if the dict variable comes from an external source
        if isinstance(node.value, ast.Name):
            var_name = node.value.id.lower()
            # Check if variable name suggests external source
            is_external = any(kw in var_name for kw in external_sources)
            if not is_external:
                continue

        key = node.slice.value
        lineno = node.lineno
        if lineno > len(lines):
            continue

        line_text = lines[lineno - 1].rstrip()
        # Generate the diff
        old_pattern = f'["{key}"]'
        new_pattern = f'.get("{key}")'

        if old_pattern not in line_text:
            continue

        new_line = line_text.replace(old_pattern, new_pattern, 1)

        diffs.append(SuggestedDiff(
            pattern="DictSubscript",
            location=f"linha {lineno}",
            line=lineno,
            confidence=0.85,
            before=line_text.strip(),
            after=new_line.strip(),
            explanation=f"Substitua dict['{key}'] por dict.get('{key}') para evitar KeyError quando a chave não existe.",
            risk_level="safe",
        ))

    return diffs


def detect_none_comparison(tree: ast.AST, code: str, lines: List[str]) -> List[SuggestedDiff]:
    """Detect == None / != None and suggest is None / is not None.

    Pattern: x == None → x is None
    """
    diffs = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for i, (op, comparator) in enumerate(zip(node.ops, node.comparators)):
            if not isinstance(comparator, ast.Constant) or comparator.value is not None:
                continue

            op_name = type(op).__name__
            if op_name not in ("Eq", "NotEq"):
                continue

            lineno = comparator.lineno
            if lineno > len(lines):
                continue

            line_text = lines[lineno - 1].rstrip()

            if op_name == "Eq":
                old_pattern = "== None"
                new_pattern = "is None"
                explanation = "Use 'is None' em vez de '== None' para comparação de identidade (PEP 8)."
            else:
                old_pattern = "!= None"
                new_pattern = "is not None"
                explanation = "Use 'is not None' em vez de '!= None' para comparação de identidade (PEP 8)."

            if old_pattern not in line_text:
                continue

            new_line = line_text.replace(old_pattern, new_pattern, 1)

            diffs.append(SuggestedDiff(
                pattern="NoneComparison",
                location=f"linha {lineno}",
                line=lineno,
                confidence=0.9,
                before=line_text.strip(),
                after=new_line.strip(),
                explanation=explanation,
                risk_level="safe",
            ))

    return diffs


def detect_range_len(tree: ast.AST, code: str, lines: List[str]) -> List[SuggestedDiff]:
    """Detect range(len()) and suggest enumerate().

    Pattern: for i in range(len(items)): → for i, item in enumerate(items):
    """
    diffs = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.iter, ast.Call):
            continue
        if not isinstance(node.iter.func, ast.Name) or node.iter.func.id != "range":
            continue
        if not node.iter.args or not isinstance(node.iter.args[0], ast.Call):
            continue
        inner_call = node.iter.args[0]
        if not isinstance(inner_call.func, ast.Name) or inner_call.func.id != "len":
            continue
        if not inner_call.args:
            continue

        # Get the variable being iterated
        if isinstance(inner_call.args[0], ast.Name):
            iterable_name = inner_call.args[0].id
        else:
            continue

        # Get the loop variable
        if isinstance(node.target, ast.Name):
            loop_var = node.target.id
        else:
            continue

        lineno = node.lineno
        if lineno > len(lines):
            continue

        line_text = lines[lineno - 1].rstrip()

        # Generate the replacement
        old_pattern = f"for {loop_var} in range(len({iterable_name}))"
        new_pattern = f"for {loop_var}, item in enumerate({iterable_name})"

        if old_pattern not in line_text:
            # Try with different spacing
            old_pattern = f"for {loop_var} in range( len( {iterable_name} ) )"
            if old_pattern not in line_text:
                continue

        new_line = line_text.replace(old_pattern, new_pattern, 1)

        diffs.append(SuggestedDiff(
            pattern="RangeLen",
            location=f"linha {lineno}",
            line=lineno,
            confidence=0.85,
            before=line_text.strip(),
            after=new_line.strip(),
            explanation=f"Use enumerate({iterable_name}) em vez de range(len({iterable_name})) para código mais Pythonico.",
            risk_level="safe",
        ))

    return diffs


def detect_bare_except(tree: ast.AST, code: str, lines: List[str]) -> List[SuggestedDiff]:
    """Detect bare except: and suggest except Exception:.

    Pattern: except: → except Exception:
    """
    diffs = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is not None:
            continue

        lineno = node.lineno
        if lineno > len(lines):
            continue

        line_text = lines[lineno - 1].rstrip()

        # Find the 'except:' pattern
        match = re.search(r'\bexcept\s*:', line_text)
        if not match:
            continue

        new_line = line_text[:match.start()] + "except Exception:" + line_text[match.end():]

        diffs.append(SuggestedDiff(
            pattern="BareExcept",
            location=f"linha {lineno}",
            line=lineno,
            confidence=0.95,
            before=line_text.strip(),
            after=new_line.strip(),
            explanation="Use 'except Exception:' em vez de 'except:' para não capturar SystemExit e KeyboardInterrupt.",
            risk_level="safe",
        ))

    return diffs


def generate_all_diffs(tree: ast.AST, code: str, filepath: str = "") -> List[SuggestedDiff]:
    """Run all 4 pattern detectors and return suggested diffs."""
    lines = code.split("\n")
    diffs = []

    for detector in [detect_dict_subscript, detect_none_comparison, detect_range_len, detect_bare_except]:
        try:
            diffs.extend(detector(tree, code, lines))
        except Exception:  # pluggable detectors may raise anything
            pass

    # Sort by line number
    diffs.sort(key=lambda d: d.line)
    return diffs
