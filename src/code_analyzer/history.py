"""History manager — persists and loads scores and metrics between runs."""
from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_project_name(filepath: Path) -> str:
    """Recursively search for project indicators to determine the project name."""
    try:
        cur = Path(filepath).resolve().parent
        for _ in range(5):
            if (cur / ".analyzer.json").exists() or (cur / "pyproject.toml").exists() or (cur / ".git").exists():
                return cur.name
            if cur.parent == cur:
                break
            cur = cur.parent
    except Exception:
        pass
    return Path.cwd().name


def get_history_dir(filepath: str) -> Path:
    """Calculate the directory for saving the analysis history of a file."""
    abs_path = str(Path(filepath).resolve())
    path_hash = hashlib.md5(abs_path.encode("utf-8")).hexdigest()
    project_name = get_project_name(Path(abs_path))
    file_stem = Path(abs_path).stem
    return Path.home() / ".code-analyzer" / "history" / project_name / f"{file_stem}_{path_hash}"


def save_history_snapshot(filepath: str, analysis: Dict[str, Any]) -> Path:
    """Save a snapshot of the analysis scores and metrics to the history folder."""
    history_dir = get_history_dir(filepath)
    history_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now()
    stamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    
    # Calcular hash do conteúdo do arquivo original para lazy evaluation
    try:
        code = Path(filepath).read_text(encoding="utf-8")
        content_hash = hashlib.md5(code.encode("utf-8")).hexdigest()
    except Exception:
        content_hash = ""
        
    # Extrair os scores de cada critério
    scores = {}
    criteria = analysis.get("criteria", {})
    for key, value in criteria.items():
        if "score" in value:
            scores[key] = value["score"]
            
    metrics = analysis.get("metrics", {})
    payload = {
        "timestamp": timestamp.isoformat(),
        "filepath": str(Path(filepath).resolve()),
        "maintainability_index": metrics.get("maintainability_index", 100.0),
        "maintainability_grade": metrics.get("maintainability_grade", "A"),
        "scores": scores,
        "content_hash": content_hash,
    }
    
    snapshot_file = history_dir / f"{stamp_str}.json"
    snapshot_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    full_file = history_dir / f"{stamp_str}_full.json"
    full_file.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    _update_index(history_dir, content_hash, stamp_str)
    return snapshot_file


def _update_index(history_dir: Path, content_hash: str, stamp_str: str) -> None:
    index_file = history_dir / ".index.json"
    index: Dict[str, str] = {}
    if index_file.exists():
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    index[content_hash] = stamp_str
    index_file.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


DEFAULT_HISTORY_LIMIT = 10

_ROI_DELTA_THRESHOLD = 0.3
_ROI_MIN_CONSECUTIVE = 2


def _snapshot_avg_score(snapshot: Dict[str, Any]) -> Optional[float]:
    scores = snapshot.get("scores", {})
    if not scores:
        return None
    vals = list(scores.values())
    return round(sum(vals) / len(vals), 2)


def check_roi_diminishing(filepath: str) -> Dict[str, Any]:
    """Return ROI analysis: whether recent runs show diminishing score gains."""
    history = load_history(filepath, limit=6)
    if len(history) < _ROI_MIN_CONSECUTIVE + 1:
        return {"roi_diminishing": False, "reason": "historico insuficiente"}

    avg_scores = []
    for snap in history:
        s = _snapshot_avg_score(snap)
        if s is not None:
            avg_scores.append(s)

    if len(avg_scores) < _ROI_MIN_CONSECUTIVE + 1:
        return {"roi_diminishing": False, "reason": "scores insuficientes no historico"}

    deltas = [avg_scores[i + 1] - avg_scores[i] for i in range(len(avg_scores) - 1)]
    small_gains = [abs(d) < _ROI_DELTA_THRESHOLD for d in deltas]

    consecutive = 0
    max_consecutive = 0
    for sg in small_gains[-_ROI_MIN_CONSECUTIVE:]:
        if sg:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    if max_consecutive >= _ROI_MIN_CONSECUTIVE:
        last_score = avg_scores[-1]
        return {
            "roi_diminishing": True,
            "consecutive_small_gains": max_consecutive,
            "avg_scores": avg_scores[-4:],
            "last_delta": round(deltas[-1], 2),
            "current_score": last_score,
            "message": (
                f"Score estavel ha {max_consecutive} execucoes consecutivas "
                f"(ultimo delta: {deltas[-1]:+.2f}). "
                "Considere: revisao manual de logica de negocio, refatoracao arquitetural "
                "profunda (ex: extrair servicos), ou analise cross-file (v3.4)."
            ),
        }

    return {
        "roi_diminishing": False,
        "avg_scores": avg_scores[-4:],
        "last_delta": round(deltas[-1], 2) if deltas else None,
    }


def load_history(filepath: str, limit: int = DEFAULT_HISTORY_LIMIT) -> List[Dict[str, Any]]:
    """Load history snapshots sorted chronologically (last N by default)."""
    history_dir = get_history_dir(filepath)
    if not history_dir.exists():
        return []
    
    index_file = history_dir / ".index.json"
    if index_file.exists():
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
            stamps = sorted(index.values())
            stamps = stamps[-limit:] if limit and len(stamps) > limit else stamps
            snapshots: List[Dict[str, Any]] = []
            for stamp in stamps:
                snapshot_file = history_dir / f"{stamp}.json"
                if snapshot_file.exists():
                    data = json.loads(snapshot_file.read_text(encoding="utf-8"))
                    snapshots.append(data)
            return snapshots
        except Exception:
            pass
    
    snapshots = []
    for file in sorted(history_dir.glob("*.json")):
        if "_full" in file.name or ".index" in file.name:
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            snapshots.append(data)
        except Exception:
            pass
    
    snapshots.sort(key=lambda s: s.get("timestamp", ""))
    if limit and len(snapshots) > limit:
        snapshots = snapshots[-limit:]
    return snapshots


def get_last_matching_snapshot(filepath: str, code: str) -> Optional[Dict[str, Any]]:
    """Check if the latest snapshot in the history matches the code hash (uses .index.json)."""
    try:
        history_dir = get_history_dir(filepath)
        index_file = history_dir / ".index.json"
        if not index_file.exists():
            return None
        index = json.loads(index_file.read_text(encoding="utf-8"))
        target_hash = hashlib.md5(code.encode("utf-8")).hexdigest()
        if target_hash in index:
            stamp_str = index[target_hash]
            full_file = history_dir / f"{stamp_str}_full.json"
            if full_file.exists():
                return json.loads(full_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None
