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
