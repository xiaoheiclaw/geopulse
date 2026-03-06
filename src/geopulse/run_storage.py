"""RunOutput archival storage — data/runs/{run_id}.json."""
from __future__ import annotations

import json
from pathlib import Path

from .run_output import RunOutput


class RunOutputStorage:
    """Manages RunOutput persistence under data/runs/."""

    def __init__(self, data_dir: Path | str):
        self.runs_dir = Path(data_dir) / "runs"

    def save(self, output: RunOutput) -> Path:
        """Archive a RunOutput and return the file path."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{output.meta.run_id}.json"
        path.write_text(
            output.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, run_id: str) -> RunOutput | None:
        """Load a RunOutput by run_id. Returns None if not found."""
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            return None
        return RunOutput.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 20) -> list[str]:
        """List archived run IDs, newest first."""
        if not self.runs_dir.exists():
            return []
        files = sorted(self.runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [f.stem for f in files[:limit]]

    def latest(self) -> RunOutput | None:
        """Load the most recent RunOutput, or None."""
        runs = self.list_runs(limit=1)
        if not runs:
            return None
        return self.load(runs[0])
