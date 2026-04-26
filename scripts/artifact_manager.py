#!/usr/bin/env python3
"""
Artifact Manager - organiza saídas da skill em uma estrutura previsível.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactRegistry:
    """Registra artefatos gerados em uma execução do pipeline."""

    source_file: Path
    output_dir: Optional[str] = None
    structured_outputs: bool = True
    timestamp: datetime = field(default_factory=datetime.now)
    records: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        source_path = Path(self.source_file).resolve()
        self.source_file = source_path

        base_dir = Path(self.output_dir).resolve() if self.output_dir else source_path.parent / ".skill_outputs"
        run_stamp = self.timestamp.strftime("%Y%m%d_%H%M%S")

        if self.structured_outputs:
            self.run_root = base_dir / source_path.stem / run_stamp
            self.analysis_dir = self.run_root / "analysis"
            self.reports_dir = self.run_root / "reports"
            self.refactors_dir = self.run_root / "refactors"
            self.backups_dir = self.run_root / "backups"
            self.tests_dir = self.run_root / "tests"
            self.logs_dir = self.run_root / "logs"
        else:
            self.run_root = base_dir
            self.analysis_dir = self.run_root
            self.reports_dir = self.run_root
            self.refactors_dir = self.run_root
            self.backups_dir = self.run_root
            self.tests_dir = self.run_root
            self.logs_dir = self.run_root

        for directory in {
            self.run_root,
            self.analysis_dir,
            self.reports_dir,
            self.refactors_dir,
            self.backups_dir,
            self.tests_dir,
            self.logs_dir,
        }:
            directory.mkdir(parents=True, exist_ok=True)

    def path_for(self, kind: str, filename: Optional[str] = None) -> Path:
        mapping = {
            "analysis": self.analysis_dir,
            "report": self.reports_dir,
            "refactor": self.refactors_dir,
            "backup": self.backups_dir,
            "test": self.tests_dir,
            "log": self.logs_dir,
        }
        base = mapping.get(kind, self.run_root)
        if filename is None:
            return base
        return base / filename

    def record(
        self,
        kind: str,
        path: Path,
        status: str = "created",
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            "kind": kind,
            "path": str(path),
            "status": status,
            "description": description,
            "metadata": metadata or {},
        }
        self.records.append(entry)
        return entry

    def manifest(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "source_file": str(self.source_file),
            "output_root": str(self.run_root),
            "structured_outputs": self.structured_outputs,
            "timestamp": self.timestamp.isoformat(),
            "directories": {
                "analysis": str(self.analysis_dir),
                "reports": str(self.reports_dir),
                "refactors": str(self.refactors_dir),
                "backups": str(self.backups_dir),
                "tests": str(self.tests_dir),
                "logs": str(self.logs_dir),
            },
            "artifacts": self.records,
        }
        if extra:
            payload["summary"] = extra
        return payload

    def save_manifest(self, extra: Optional[Dict[str, Any]] = None) -> Path:
        manifest_path = self.logs_dir / "execution_manifest.json"
        manifest_path.write_text(
            json.dumps(self.manifest(extra), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return manifest_path
