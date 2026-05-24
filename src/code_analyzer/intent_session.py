"""Intent Learning session — conversational UI that connects IL1/IL2/IL4 to the developer.

Flow:
  1. build_question_queue() filters findings with confidence < 0.70, ranked by impact
  2. User answers each question (s=intencional / n=bug / c=outro mecanismo / ?=pular)
  3. IntentStore persists every non-skip answer to .analyzer_intent.json
  4. apply_intents() returns updated criteria: silenced removed, bugs forced to confidence=1.0
  5. _phase2_proposition receives the cleaned criteria for reports

Skips silently when:
  - Not a TTY (CI, pipes, --json)
  - --quiet flag (non-interactive run)
  - limit=0 (caller explicitly disables questions)
  - No low-confidence findings in the queue
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

from code_analyzer.analyzer.detection_runner import build_question_queue
from code_analyzer.intent_store import IntentStore, apply_intents

_SEP = "─" * 54
_SEP2 = "═" * 54

_ANSWER_MAP: Dict[str, str] = {
    "s": "intentional",
    "n": "bug",
    "c": "other_mechanism",
    "?": "skip",
}

_ANSWER_FEEDBACK: Dict[str, str] = {
    "intentional":      "+ Registrado — silenciado nos proximos runs.",
    "bug":              "+ Registrado — confidence 1.0 nos proximos runs.",
    "other_mechanism":  "+ Registrado — silenciado com nota.",
    "skip":             "  Pulado — perguntarei de novo na proxima vez.",
}


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _wrap(text: str, width: int = 64, indent: str = "  ") -> None:
    """Print text wrapped at width, each line prefixed with indent."""
    words = text.split()
    line: List[str] = []
    length = 0
    for w in words:
        if length + len(w) + 1 > width and line:
            print(f"{indent}{'  '.join(line)}")
            line, length = [], 0
        line.append(w)
        length += len(w) + 1
    if line:
        print(f"{indent}{' '.join(line)}")


def _ask_intent(question: Dict[str, Any], idx: int, total: int) -> Tuple[str, str]:
    """Display one question and return (answer_key, note). Raises KeyboardInterrupt on Ctrl+C."""
    impact = question.get("impact", 0)
    print(f"\n  {_SEP}")
    print(f"  Pergunta {idx}/{total}  [{question['criterion']}  impacto: {impact:.0f}]")
    print(f"  {_SEP}")
    print(f"  > {question['location']}")
    content = question.get("line_content", "").strip()
    if content:
        print(f"    {content[:80]}")
    print()
    _wrap(question.get("issue", ""), width=62)
    print()
    print("   [s] intencional — correto por design")
    print("   [n] bug real    — precisa correcao")
    print("   [c] outro mecanismo — outra camada cobre isso")
    print("   [?] pular       — perguntar de novo na proxima vez")

    raw = input("\n  Resposta [s/n/c/?]: ").strip().lower()
    if raw not in _ANSWER_MAP:
        raw = "?"
    answer = _ANSWER_MAP[raw]

    note = ""
    if answer == "other_mechanism":
        note = input("  Nota (descreva o mecanismo, opcional): ").strip()

    return answer, note


def run_intent_session(
    filepath: str,
    criteria: Dict[str, Any],
    intent_store: IntentStore,
    limit: int = 3,
    ask_questions: bool = True,
) -> Dict[str, Any]:
    """Run the conversational Q&A session and return updated criteria.

    When *ask_questions* is False or the environment is non-interactive,
    only apply existing intents without asking new questions.
    """
    # Always apply existing stored answers first
    if not ask_questions or limit == 0 or not _is_tty():
        return apply_intents(criteria, intent_store)

    queue = build_question_queue(criteria, limit=limit, intent_store=intent_store)
    if not queue:
        return apply_intents(criteria, intent_store)

    n = len(queue)
    print(f"\n  Tenho {n} pergunta(s) para refinar a analise.")
    print("  Responder ajuda a reduzir falsos positivos nos proximos runs.")

    try:
        confirm = input("\n  Responder agora? [s/n/depois]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return apply_intents(criteria, intent_store)

    if confirm not in ("s", "sim", "y", "yes"):
        return apply_intents(criteria, intent_store)

    learned: List[Tuple[str, str, str]] = []
    for idx, question in enumerate(queue, 1):
        try:
            answer, note = _ask_intent(question, idx, n)
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Sessao interrompida. Respostas anteriores foram salvas.")
            break

        intent_store.save(
            question["finding_id"],
            answer,
            note=note,
            criterion=question["criterion"],
            location=question["location"],
        )
        print(f"\n  {_ANSWER_FEEDBACK.get(answer, '')}")

        if answer != "skip":
            learned.append((question["criterion"], question["location"], answer))

    if learned:
        print(f"\n  {_SEP2}")
        print(f"  Aprendi {len(learned)} coisa(s) sobre seu projeto:")
        for criterion, location, answer in learned:
            tag = "silenciado" if answer != "bug" else "bug confirmado"
            print(f"    + {criterion} em {location} ({tag})")
        print(f"  Salvo em: .analyzer_intent.json")
        print(f"  {_SEP2}")

    return apply_intents(criteria, intent_store)
