"""DAG persistence: save, load, history snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import DAG


class DAGStorage:
    """Manages DAG file storage with versioned history snapshots."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.dag_path = self.data_dir / "dag.json"
        self.history_dir = self.data_dir / "history"

    def save(self, dag: DAG) -> Path:
        """Save DAG to disk, incrementing version and creating a history snapshot."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        existing = self.load()
        if existing is not None:
            dag.version = existing.version + 1

        dag.updated = datetime.now(timezone.utc)
        self.dag_path.write_text(dag.to_json(), encoding="utf-8")

        ts = dag.updated.strftime("%Y-%m-%dT%H%M%S_%f")
        snapshot_path = self.history_dir / f"{ts}.json"
        snapshot_path.write_text(dag.to_json(), encoding="utf-8")

        return self.dag_path

    def load(self) -> DAG | None:
        """Load the current DAG from disk, or None if not found."""
        if not self.dag_path.exists():
            return None
        return DAG.from_json(self.dag_path.read_text(encoding="utf-8"))

    def list_history(self) -> list[str]:
        """List history snapshot filenames, newest first."""
        if not self.history_dir.exists():
            return []
        return sorted(
            (p.name for p in self.history_dir.glob("*.json")), reverse=True
        )

    def load_snapshot(self, filename: str) -> DAG:
        """Load a specific history snapshot by filename."""
        path = self.history_dir / filename
        return DAG.from_json(path.read_text(encoding="utf-8"))
