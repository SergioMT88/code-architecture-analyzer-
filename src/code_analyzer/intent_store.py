"""IntentStore — persists user answers to clarifying questions in .analyzer_intent.json.

Answers drive two downstream effects (applied by apply_intents):
  - "bug"              → finding stays, confidence forced to 1.0
  - "intentional"      → finding silenced (removed from report)
  - "other_mechanism"  → finding silenced with explanatory note
  - "skip"             → NOT persisted, question asked again next run
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_INTENT_FILE = ".analyzer_intent.json"
_LEGACY_FILE = ".analyzer_silenced.json"
_FORMAT_VERSION = 1
_SILENCED_ANSWERS = frozenset({"intentional", "other_mechanism"})


def _git_user() -> str:
    try:
        r = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


class IntentStore:
    """Loads, queries, and persists intent answers for a project."""

    def __init__(self, project_root: str) -> None:
        self._root = Path(project_root)
        self._path = self._root / _INTENT_FILE
        self._data: Dict[str, Any] = {"_version": _FORMAT_VERSION, "intents": {}}
        self._load()

    # ------------------------------------------------------------------ load/save

    def _load(self) -> None:
        legacy = self._root / _LEGACY_FILE
        if legacy.exists() and not self._path.exists():
            self._migrate_legacy(legacy)
            return
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = raw
        except Exception:
            pass  # corrupt file — start fresh, don't crash

    def _write(self) -> None:
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _migrate_legacy(self, legacy_path: Path) -> None:
        """Convert .analyzer_silenced.json → .analyzer_intent.json and remove old file."""
        try:
            old = json.loads(legacy_path.read_text(encoding="utf-8"))
        except Exception:
            return
        intents: Dict[str, Any] = {}
        for fid, entry in old.items():
            if fid.startswith("_"):
                continue
            intents[fid] = {
                "answer": "intentional",
                "note": entry.get("reason", ""),
                "asked_at": entry.get("silenced_at", _now_iso()),
                "answered_by": "unknown",
                "criterion": "",
                "location": "",
            }
        self._data = {"_version": _FORMAT_VERSION, "intents": intents}
        self._write()
        try:
            legacy_path.unlink()
        except Exception:
            pass

    # ------------------------------------------------------------------ public API

    def get(self, finding_id: str) -> Optional[dict]:
        """Return stored intent or None."""
        return self._data.get("intents", {}).get(finding_id)

    def save(
        self,
        finding_id: str,
        answer: str,
        note: str = "",
        criterion: str = "",
        location: str = "",
    ) -> None:
        """Persist an answer. Silently ignores answer == 'skip'."""
        if answer == "skip":
            return
        self._data.setdefault("intents", {})[finding_id] = {
            "answer": answer,
            "note": note,
            "asked_at": _now_iso(),
            "answered_by": _git_user(),
            "criterion": criterion,
            "location": location,
        }
        self._write()

    def is_silenced(self, finding_id: str) -> bool:
        intent = self.get(finding_id)
        return intent is not None and intent.get("answer") in _SILENCED_ANSWERS

    def is_confirmed(self, finding_id: str) -> bool:
        intent = self.get(finding_id)
        return intent is not None and intent.get("answer") == "bug"

    def all_intents(self) -> Dict[str, Any]:
        return dict(self._data.get("intents", {}))

    def criteria_stats(self) -> List[Dict[str, Any]]:
        """Per-criterion aggregation of stored answers, sorted by total answers desc.

        Each entry: {criterion, total, fp_count, bug_count, fp_rate, bug_rate, label}
        Labels: ruidoso | saudável | misto | insuficiente
        """
        _FP_ANSWERS = frozenset({"intentional", "other_mechanism"})
        _MIN = 10
        _THRESHOLD = 0.7

        totals: Dict[str, int] = {}
        fp_counts: Dict[str, int] = {}
        bug_counts: Dict[str, int] = {}
        for entry in self._data.get("intents", {}).values():
            crit = entry.get("criterion", "")
            if not crit:
                continue
            totals[crit] = totals.get(crit, 0) + 1
            if entry.get("answer") in _FP_ANSWERS:
                fp_counts[crit] = fp_counts.get(crit, 0) + 1
            elif entry.get("answer") == "bug":
                bug_counts[crit] = bug_counts.get(crit, 0) + 1

        rows: List[Dict[str, Any]] = []
        for crit, total in totals.items():
            fp_c = fp_counts.get(crit, 0)
            bug_c = bug_counts.get(crit, 0)
            fp_rate = fp_c / total
            bug_rate = bug_c / total
            if total < _MIN:
                label = "insuficiente"
            elif fp_rate >= _THRESHOLD:
                label = "ruidoso"
            elif bug_rate >= _THRESHOLD:
                label = "saudável"
            else:
                label = "misto"
            rows.append(
                {
                    "criterion": crit,
                    "total": total,
                    "fp_count": fp_c,
                    "bug_count": bug_c,
                    "fp_rate": fp_rate,
                    "bug_rate": bug_rate,
                    "label": label,
                }
            )
        rows.sort(key=lambda r: -r["total"])
        return rows

    def noisy_criteria(
        self, min_answers: int = 10, fp_threshold: float = 0.7
    ) -> Dict[str, float]:
        """Return {criterion: fp_rate} for criteria answered as non-bug >= fp_threshold of the time.

        A criterion is "noisy" for this project when the local answer history shows
        most findings are intentional/other_mechanism rather than real bugs.
        Requires min_answers answers to avoid false positives from small samples.
        """
        _FP_ANSWERS = frozenset({"intentional", "other_mechanism"})
        totals: Dict[str, int] = {}
        fp_counts: Dict[str, int] = {}
        for entry in self._data.get("intents", {}).values():
            crit = entry.get("criterion", "")
            if not crit:
                continue
            totals[crit] = totals.get(crit, 0) + 1
            if entry.get("answer") in _FP_ANSWERS:
                fp_counts[crit] = fp_counts.get(crit, 0) + 1
        result: Dict[str, float] = {}
        for crit, total in totals.items():
            if total >= min_answers:
                fp_rate = fp_counts.get(crit, 0) / total
                if fp_rate >= fp_threshold:
                    result[crit] = fp_rate
        return result


# ------------------------------------------------------------------ post-processing


def apply_intents(
    criteria: Dict[str, Any],
    intent_store: IntentStore,
) -> Dict[str, Any]:
    """Return a new criteria dict with intent answers applied.

    - Silenced findings are removed; score is recalculated.
    - Confirmed bugs get confidence forced to 1.0.
    - Noisy criteria (IL8) get penalty_per_finding=0 based on local answer history.
    """
    from code_analyzer.analyzer.scoring import score_to_status

    noisy = intent_store.noisy_criteria()
    result: Dict[str, Any] = {}
    for name, criterion in criteria.items():
        penalty = criterion.get("penalty_per_finding", 2)
        kept: List[dict] = []
        for f in criterion.get("findings", []):
            fid = f.get("finding_id", "")
            if intent_store.is_silenced(fid):
                continue
            if intent_store.is_confirmed(fid):
                f = {**f, "confidence": 1.0}
            kept.append(f)
        noisy_extras: Dict[str, Any] = {}
        if name in noisy:
            penalty = 0
            noisy_extras = {"noisy": True, "noisy_fp_rate": noisy[name]}
        score = max(0, 10 - len(kept) * penalty)
        result[name] = {
            **criterion,
            **noisy_extras,
            "findings": kept,
            "score": score,
            "status": score_to_status(score),
            "penalty_per_finding": penalty,
        }
    return result
