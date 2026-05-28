"""Agent-friendly output — structured Markdown or JSON action plan for AI coding agents.

For JSON output (agent mode), delegates to analyzer/action_plan.py (v7.0).
For Markdown output, uses the legacy advice dictionary (v4.4+).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from code_analyzer.terminal_ui import ScoreBundle

# ---------------------------------------------------------------------------
# Per-criterion advice dictionary
# ---------------------------------------------------------------------------

_ADVICE: Dict[str, Dict[str, Any]] = {
    "GodClass": {
        "why": "A single large class makes every change risky and testing hard.",
        "fix": [
            "Identify groups of methods that access the same subset of attributes.",
            "Extract each group into its own class with a clear single responsibility.",
            "Use dependency injection to connect extracted classes.",
            "Keep the original class as a thin coordinator if needed.",
        ],
        "pattern": "Extract Class → Single Responsibility Principle",
    },
    "CircularDeps": {
        "why": "Circular imports cause import errors in tests and block safe refactoring.",
        "fix": [
            "Create a shared module (e.g., protocols.py or interfaces.py) for shared types.",
            "Move shared interfaces/protocols/ABCs there.",
            "Both modules import from the shared module, not from each other.",
        ],
        "pattern": "Dependency Inversion → break cycle via abstraction layer",
    },
    "Coupling": {
        "why": "High import count means any external change can break this file.",
        "fix": [
            "Group imports by domain (models, services, utils, external).",
            "Create a Facade class that wraps each domain's dependencies.",
            "This file depends only on the Facades, not the raw dependencies.",
        ],
        "pattern": "Facade Pattern → reduce direct coupling",
    },
    "SRP": {
        "why": "Class has too many responsibilities — changes in one area affect others.",
        "fix": [
            "List the distinct verbs this class performs (create, send, validate, log...).",
            "Each verb is a responsibility — extract it into its own class.",
        ],
        "pattern": "Extract Class → Single Responsibility",
    },
    "DeepNesting": {
        "why": "Deep nesting makes code hard to read, test, and modify.",
        "fix": [
            "Apply Early Return: invert conditions to return/continue/break early.",
            "Extract nested blocks into separate functions with descriptive names.",
        ],
        "pattern": "Early Return Pattern → flatten control flow",
    },
    "Cohesion": {
        "why": "Methods access disjoint sets of attributes — class is doing multiple things.",
        "fix": [
            "Group attributes and the methods that use them together.",
            "Extract each group into a focused, cohesive class.",
        ],
        "pattern": "Extract Class → High Cohesion",
    },
    "DIP": {
        "why": "Depending on concrete classes makes testing and extension harder.",
        "fix": [
            "Create an Abstract Base Class or Protocol for each key dependency.",
            "Inject the dependency via __init__ instead of instantiating it directly.",
        ],
        "pattern": "Dependency Injection → depend on abstractions",
    },
    "InterfaceSegregation": {
        "why": "Large public interface forces clients to depend on methods they don't use.",
        "fix": [
            "Identify which methods each client actually calls.",
            "Split into smaller interfaces/protocols matching each client's actual needs.",
        ],
        "pattern": "Interface Segregation → smaller, focused interfaces",
    },
    "HardcodedSecrets": {
        "why": "Credentials in source code leak via git history even after removal.",
        "fix": [
            "Move to environment variables: os.environ.get('KEY_NAME').",
            "Use a .env file with python-dotenv — never commit it.",
            "Rotate any exposed credentials immediately.",
        ],
        "pattern": "Environment Configuration → no secrets in code",
    },
    "InjectionRisk": {
        "why": "User-controlled input in SQL/shell commands enables injection attacks.",
        "fix": [
            "Use parameterized queries instead of f-strings in SQL.",
            "Use subprocess with a list of args instead of shell=True with f-strings.",
        ],
        "pattern": "Parameterized inputs → prevent injection",
    },
    "OrmInLoop": {
        "why": "One database query per loop iteration — N queries for N records.",
        "fix": [
            "Use select_related() for ForeignKey/OneToOne relationships.",
            "Use prefetch_related() for ManyToMany/reverse FK relationships.",
            "Move the queryset construction outside the loop.",
        ],
        "pattern": "Batch query → prevent N+1 problem",
    },
    "FeatureEnvy": {
        "why": "Method uses another object's data more than its own — wrong class placement.",
        "fix": [
            "Move the method to the class whose data it uses the most.",
            "Or extract the data it needs into a parameter (reduce envy).",
        ],
        "pattern": "Move Method → correct class placement",
    },
    "ShotgunSurgery": {
        "why": "A single change requires touching many classes — fragile design.",
        "fix": [
            "Centralize the concept that is scattered across classes.",
            "Use a single class or module as the authoritative source.",
        ],
        "pattern": "Consolidate → reduce change shotgun",
    },
    "MassAssignment": {
        "why": "fields='__all__' exposes every model field to user input — security risk.",
        "fix": [
            "Replace with explicit fields list: fields = ['field1', 'field2', ...]",
            "Or use exclude = ['sensitive_field'] to blocklist sensitive fields.",
        ],
        "pattern": "Explicit field listing → prevent mass assignment",
    },
    "SaveSideEffects": {
        "why": "I/O operations inside model.save() are called unexpectedly on every save.",
        "fix": [
            "Move side effects (email, HTTP calls) to a service layer or signal handler.",
            "Keep save() pure — only persist data.",
        ],
        "pattern": "Extract side effects → pure persistence methods",
    },
    "ContextManagerLeak": {
        "why": "open() without with statement leaks file handles on exception.",
        "fix": [
            "Wrap every open() call in a with statement.",
        ],
        "pattern": "Context Manager → guaranteed resource cleanup",
    },
}

# Priority order for execution (fix blockers first)
_PRIORITY_ORDER = [
    "CircularDeps",
    "HardcodedSecrets",
    "InjectionRisk",
    "GodClass",
    "SRP",
    "Coupling",
    "OrmInLoop",
    "MassAssignment",
    "SaveSideEffects",
    "DeepNesting",
    "FeatureEnvy",
    "ShotgunSurgery",
    "ContextManagerLeak",
    "Cohesion",
    "DIP",
    "InterfaceSegregation",
]

_PRIORITY_REASON: Dict[str, str] = {
    "CircularDeps": "unblocks safe refactoring",
    "HardcodedSecrets": "security — fix immediately",
    "InjectionRisk": "security — fix immediately",
    "GodClass": "biggest structural issue",
    "SRP": "structural integrity",
    "Coupling": "enables other refactors",
    "OrmInLoop": "performance — high user impact",
}


def _sort_key(name: str) -> int:
    try:
        return _PRIORITY_ORDER.index(name)
    except ValueError:
        return 99


def _extract_class_info(findings: List[Dict]) -> str:
    """Extract class name/size from GodClass finding text."""
    for f in findings:
        issue = f.get("issue", "")
        m = re.search(r"'(\w+)'.*?(\d+) linhas.*?(\d+) metod", issue)
        if m:
            return f" ({m.group(1)}, {m.group(2)} lines, {m.group(3)} methods)"
        m2 = re.search(r"'(\w+)'", issue)
        if m2:
            return f" ({m2.group(1)})"
    return ""


def _format_locations(findings: List[Dict], limit: int = 4) -> str:
    locs = []
    for f in findings[:limit]:
        loc = f.get("location", "")
        if loc:
            locs.append(loc)
    return " | ".join(locs) if locs else ""


def _format_critical(priority: int, name: str, data: Dict) -> List[str]:
    findings = data.get("findings", [])
    adv = _ADVICE.get(name, {})
    out = []

    suffix = _extract_class_info(findings) if name == "GodClass" else ""
    out.append(f"### Priority {priority} [CRITICAL] — {name}{suffix}")

    loc = _format_locations(findings)
    if loc:
        out.append(f"Location: {loc}")

    why = adv.get("why", data.get("description", ""))
    if why:
        out.append(f"**Why it matters:** {why}")

    fix_steps = adv.get("fix", [])
    if fix_steps:
        out.append("**How to fix:**")
        for i, step in enumerate(fix_steps, 1):
            out.append(f"  {i}. {step}")
    elif findings:
        suggestion = findings[0].get("suggestion", "")
        if suggestion:
            out.append(f"**Fix:** {suggestion}")

    pattern = adv.get("pattern", "")
    if pattern:
        out.append(f"**Pattern:** {pattern}")

    return out


def _get_il_summary(analysis: Dict) -> Tuple[int, List[str]]:
    """Return (answer_count, noisy_criteria_list)."""
    criteria = analysis.get("criteria", {})
    noisy = [n for n, v in criteria.items() if v.get("noisy")]
    # Estimate answer count from intent data if available
    il_data = analysis.get("_intent_answers", 0)
    return il_data, noisy


def generate_agent_output(
    analysis: Dict[str, Any],
    sb: ScoreBundle,
    filepath: str,
    il_answer_count: int = 0,
) -> str:
    filename = Path(filepath).name
    criteria = analysis.get("criteria", {})

    criticals = sorted(
        [(n, v) for n, v in criteria.items() if v.get("score", 10) < 5],
        key=lambda x: _sort_key(x[0]),
    )
    warnings = [(n, v) for n, v in criteria.items() if 5 <= v.get("score", 10) < 7]
    noisy = [n for n, v in criteria.items() if v.get("noisy")]

    lines: List[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append(f"# ANALYSIS: {filename} — Score {sb.avg_score}/10 ({sb.grade})")
    lines.append(
        f"MI: {sb.mi:.1f} ({sb.mg}) | "
        f"Production Risk: {sb.risk_label} ({sb.risk_score:.1f}/100)"
    )
    lines.append(
        f"{len(criticals)} critical | {len(warnings)} warnings | "
        f"{sb.total_findings} total findings"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Action plan ─────────────────────────────────────────────────────────
    if criticals:
        lines.append("## ACTION PLAN")
        lines.append("")
        for i, (name, data) in enumerate(criticals, 1):
            lines.extend(_format_critical(i, name, data))
            lines.append("")

    # ── Warnings ────────────────────────────────────────────────────────────
    if warnings:
        lines.append("---")
        lines.append("")
        lines.append("## WARNINGS (address after criticals)")
        lines.append("")
        for name, data in warnings:
            findings = data.get("findings", [])
            loc = _format_locations(findings, limit=2)
            adv = _ADVICE.get(name, {})
            why = adv.get("why", data.get("description", ""))
            pattern = adv.get("pattern", "")
            entry = f"- **{name}**"
            if loc:
                entry += f" [{loc}]"
            if why:
                entry += f" — {why}"
            lines.append(entry)
            if pattern:
                lines.append(f"  Pattern: {pattern}")
        lines.append("")

    # ── Intent Learning status ───────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## INTENT LEARNING")
    if noisy:
        lines.append(
            f"Detectors in informational mode (findings silenced — marked as "
            f"non-issues in this project): {', '.join(noisy)}"
        )
    elif il_answer_count > 0:
        lines.append(
            f"{il_answer_count} answers recorded. "
            "No detectors silenced yet — keep answering to build the profile."
        )
    else:
        lines.append("No answers recorded yet for this project.")
        lines.append(
            "Run analysis interactively (without --agent) to teach the tool "
            "which findings are real issues here."
        )
    lines.append("")

    # ── Execution order ──────────────────────────────────────────────────────
    ordered = [n for n in _PRIORITY_ORDER if n in dict(criticals)]
    if ordered:
        lines.append("---")
        lines.append("")
        lines.append("## EXECUTION ORDER")
        for i, name in enumerate(ordered, 1):
            reason = _PRIORITY_REASON.get(name, "")
            suffix = f" — {reason}" if reason else ""
            lines.append(f"{i}. **{name}**{suffix}")
        lines.append("")

    # ── Metadata ─────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## METADATA")
    lines.append(
        f"Score: {sb.avg_score}/10 | Grade: {sb.grade} | "
        f"MI: {sb.mi:.1f} | Risk: {sb.risk_score:.1f}/100"
    )
    lines.append(
        f"Critical: {len(criticals)} | Warnings: {len(warnings)} | "
        f"Total findings: {sb.total_findings}"
    )
    lines.append(f"File: {filepath}")

    return "\n".join(lines)


def generate_agent_json(
    filepath: str,
    analysis: Dict[str, Any],
    il_answer_count: int = 0,
) -> str:
    """Generate JSON output with full ActionRecords for AI coding agents.

    This is the primary output format for --agent mode (v7.0).
    Delegates to analyzer/action_plan.py.
    """
    from code_analyzer.analyzer.action_plan import generate_agent_json as _ga_json
    return _ga_json(filepath, analysis, il_answer_count)
