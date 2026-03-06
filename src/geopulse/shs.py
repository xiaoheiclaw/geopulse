"""Standing Hypothesis Set — Agent's cross-run memory system.

Each hypothesis is a structured, falsifiable claim about the geopolitical
situation. The SHS is loaded before each run and written back after.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .run_output import SHSAction, SHSWriteback


class Hypothesis(BaseModel):
    """A standing hypothesis in the Agent's memory."""

    id: str
    label: str  # "有限冲突" / "全面升级" etc.
    statement: str  # Full hypothesis statement
    trigger_signals: list[str] = Field(default_factory=list)
    invalidation_signals: list[str] = Field(default_factory=list)
    observed_entities: list[str] = Field(default_factory=list)
    horizon: str = ""  # "W1_5" | "W6_16" | "W17_25plus"
    asset_expression: str = ""  # "long oil vol" etc.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: str = "active"  # "active" | "deprecated"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_run_ids: list[str] = Field(default_factory=list)


class SHSStorage:
    """Manages SHS persistence to data/shs.json."""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.shs_path = self.data_dir / "shs.json"

    def load(self) -> list[Hypothesis]:
        """Load hypotheses from disk. Returns empty list if not found."""
        if not self.shs_path.exists():
            return []
        raw = json.loads(self.shs_path.read_text(encoding="utf-8"))
        return [Hypothesis.model_validate(h) for h in raw]

    def save(self, hypotheses: list[Hypothesis]) -> None:
        """Save hypotheses to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = [h.model_dump(mode="json") for h in hypotheses]
        self.shs_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def apply_writebacks(
        self, writebacks: list[SHSWriteback], run_id: str
    ) -> list[Hypothesis]:
        """Apply Agent's SHS writebacks and persist.

        Returns the updated hypothesis list.
        """
        hypotheses = self.load()
        by_ref = {h.id: h for h in hypotheses}
        # Also index by label for fuzzy matching
        by_label = {h.label: h for h in hypotheses}

        now = datetime.now(timezone.utc)

        for wb in writebacks:
            existing = by_ref.get(wb.hypothesis_ref) or by_label.get(
                wb.hypothesis_ref
            )

            if wb.action == SHSAction.add:
                if existing:
                    # Already exists — treat as update
                    _apply_field_update(existing, wb, run_id, now)
                else:
                    new_h = Hypothesis(
                        id=wb.hypothesis_ref,
                        label=wb.hypothesis_ref,
                        statement=wb.new_value,
                        confidence=0.5,
                        created_at=now,
                        updated_at=now,
                        source_run_ids=[run_id],
                    )
                    hypotheses.append(new_h)
                    by_ref[new_h.id] = new_h
                    by_label[new_h.label] = new_h

            elif wb.action == SHSAction.update:
                if existing:
                    _apply_field_update(existing, wb, run_id, now)

            elif wb.action == SHSAction.deprecate:
                if existing:
                    existing.status = "deprecated"
                    existing.updated_at = now
                    if run_id not in existing.source_run_ids:
                        existing.source_run_ids.append(run_id)

        self.save(hypotheses)
        return hypotheses


def _apply_field_update(
    h: Hypothesis, wb: SHSWriteback, run_id: str, now: datetime
) -> None:
    """Apply a single field update to a hypothesis."""
    field = wb.field_changed
    if hasattr(h, field):
        current_val = getattr(h, field)
        if isinstance(current_val, float):
            try:
                setattr(h, field, float(wb.new_value))
            except ValueError:
                pass
        elif isinstance(current_val, list):
            # For list fields, append the new value
            current_val.append(wb.new_value)
        else:
            setattr(h, field, wb.new_value)
    h.updated_at = now
    if run_id not in h.source_run_ids:
        h.source_run_ids.append(run_id)
