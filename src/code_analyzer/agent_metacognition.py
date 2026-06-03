"""Shared metacognitive knowledge for agent output [v7.3.0].

Single source of truth for the "why / impact / think-step-by-step" scaffolding
that makes an AI coding agent reason before editing. Both the unified agent JSON
(`analyzer/action_plan.py`) and the legacy Markdown review (`agent_review.py`)
read from here, so the metacognition is consistent across every entry point.

Before v7.3 these maps were duplicated inside agent_review and covered only ~10
of 53 detectors; everything else degraded to a generic sentence. Centralizing
them here is also where the coverage gets widened.
"""
from __future__ import annotations

from typing import Optional

# Why each finding is a problem — the metacognitive "stop and understand" line.
REASONING_MAP = {
    # structure / SOLID
    "SRP": "This class has more than one reason to change. When you touch one "
           "responsibility you risk breaking another. Split responsibilities so "
           "each class changes for a single reason.",
    "GodClass": "This class does too much — it concentrates state and behavior that "
                "belong to several concerns. Large classes are hard to test, hard to "
                "reason about, and are the #1 source of bugs in big codebases.",
    "Coupling": "This module depends on too many others, so external changes ripple "
                "into it. Loose coupling makes the system easier to change and test.",
    "Cohesion": "The methods here operate on disjoint sets of attributes — the class "
                "is really several classes wearing one name. Group what belongs together.",
    "DeepNesting": "Each nesting level adds cognitive load and hides the happy path. "
                   "Invert conditions to return early, or extract the inner block.",
    "FeatureEnvy": "This method uses another object's data more than its own. It most "
                   "likely belongs in that other class — move it closer to the data.",
    "DIP": "Depending on a concrete class hard-wires this code to one implementation, "
           "making it rigid and hard to test. Depend on an abstraction injected in.",
    "InterfaceSegregation": "A fat interface forces clients to depend on methods they "
                            "never call. Split it into the smaller roles each client uses.",
    "OCP": "Adding a new case here means editing existing code instead of extending it. "
           "Replace the branching with polymorphism so new cases are additive.",
    "LSP": "A subclass that weakens guarantees (raising where the base didn't, or "
           "strengthening a precondition) breaks code written against the base type.",
    "StringDispatch": "Dispatching on string values scatters behavior and invites typos. "
                      "A mapping or polymorphism makes the cases explicit and checkable.",
    "ShotgunSurgery": "One conceptual change forces edits in many places. Centralize the "
                      "scattered concept so a single edit suffices.",
    "HighFanIn": (
        "This symbol is imported by 5+ other modules — it is a structural "
        "coupling hotspot. Any change to its interface will break all callers "
        "simultaneously. Treat it like a public API: stabilize it or narrow it."
    ),
    # security / correctness
    "HardcodedSecrets": "A credential in source code leaks through git history forever, "
                        "even after you delete it. Load it from the environment instead.",
    "InjectionRisk": "User-controlled input flowing into SQL or a shell command lets an "
                     "attacker run their own code. Parameterize the query / pass args as a list.",
    "MassAssignment": "Binding user input straight onto a model lets a caller set fields "
                      "you never intended (e.g. is_admin). List the allowed fields explicitly.",
    "ContextManagerLeak": "open() without `with` leaks the handle if an exception fires "
                          "before close(). Use a context manager so cleanup is guaranteed.",
    "BareExcept": "A bare `except:` swallows everything — including KeyboardInterrupt and "
                  "real bugs — and hides the cause. Catch the specific exception you expect.",
    "MutableDefault": "A mutable default argument is shared across all calls, so state "
                      "leaks between invocations. Default to None and create it inside.",
    "OrmInLoop": "A query per loop iteration is the N+1 problem — N records means N round "
                 "trips. Fetch related rows in one query before the loop.",
    "SaveSideEffects": "I/O (email, HTTP) inside save() runs on every persist, often "
                       "unexpectedly. Keep save() pure and move effects to a service/signal.",
    # python idioms
    "PrintLeak": "A debug print left in production pollutes stdout and can leak data. "
                 "Use the logging module so output level is controllable.",
    "ManualAccumulate": "A manual append loop is verbose and easy to get wrong. A "
                        "comprehension states the intent in one line and is often faster.",
    "DictGet": "Indexing a dict that may lack the key raises KeyError at runtime. "
               "`.get(key, default)` makes the missing-key path explicit.",
    "NoneComparison": "`== None` relies on __eq__, which can be overloaded or wrong. "
                      "`is None` checks identity and is the correct idiom.",
    "RangeLenLoop": "`for i in range(len(xs))` then `xs[i]` hides intent. `enumerate(xs)` "
                    "gives index and value directly.",
    "WildcardImport": "`from m import *` pulls unknown names into scope, shadowing locals "
                      "and breaking tooling. Import the specific names you use.",
    "ManyParameters": "A long parameter list signals the function does too much or wants "
                      "an object. Group related params into a small dataclass.",
    "TypeIsInstance": "`type(x) == T` fails for subclasses. `isinstance(x, T)` is the "
                      "correct, subclass-aware check.",
    "InconsistentReturns": "A function returning different shapes on different paths is "
                           "unpredictable for callers. Return one consistent type.",
}

_IMPACT_BASE = {
    "CRITICA": "Critical: can cause bugs, security holes, or make the code unmaintainable.",
    "ALTA": "High: significantly hurts maintainability and reliability.",
    "MEDIA": "Medium: worth fixing when you touch this area.",
    "BAIXA": "Low: a polish item that improves quality.",
}

_IMPACT_SPECIFIC = {
    "HardcodedSecrets": "a leaked credential can compromise the whole system.",
    "InjectionRisk": "an injection can lead to data theft or remote code execution.",
    "MassAssignment": "an attacker may set privileged fields you never exposed.",
    "OrmInLoop": "N+1 queries can melt performance under real load.",
    "GodClass": "god classes accumulate bugs and block safe refactoring.",
    "ShotgunSurgery": "scattered edits mean changes are slow and easy to get wrong.",
    "HighFanIn": "every interface change forces parallel edits across many callers.",
}


def reasoning_for(criterion: str) -> str:
    return REASONING_MAP.get(
        criterion,
        "This finding flags a code-quality issue worth understanding before editing.",
    )


def impact_for(criterion: str, severity: str) -> str:
    base = _IMPACT_BASE.get(severity, _IMPACT_BASE["MEDIA"])
    specific = _IMPACT_SPECIFIC.get(criterion)
    return f"{base} Specifically: {specific}" if specific else base


def build_metacognitive_guide(
    *,
    critical: int,
    warnings: int,
    total_findings: int,
    cross_file: int = 0,
    score: Optional[float] = None,
    grade: Optional[str] = None,
) -> str:
    """Build the think-before-you-code guide injected into the agent envelope."""
    head = []
    if score is not None:
        head.append(f"Score {score}/10 ({grade or '-'}).")
    head.append(
        f"{total_findings} findings: {critical} critical, {warnings} warnings"
        + (f", {cross_file} cross-file." if cross_file else ".")
    )
    return (
        " ".join(head)
        + "\n\nThink step by step before editing:\n"
        "1. Read each finding's `reasoning` — understand WHY it's a problem, not just what.\n"
        "2. Fix `severity: ALTA` items first (security/correctness), then MEDIA, then BAIXA.\n"
        "3. Cross-file findings (e.g. a value duplicated across modules) usually mean a "
        "single change in many places — fix the root, not each copy.\n"
        "4. Prefer the `diff` when present — it's a safe, mechanical transformation.\n"
        "5. After each fix, run the record's `verify` steps; don't batch blindly.\n"
        "6. Re-run `code-analyze` to confirm the score moved and no regression appeared.\n"
        "7. If a finding is wrong for this project, record it (Intent Learning) so it "
        "stops being surfaced — don't just ignore it."
    )
