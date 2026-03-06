"""Tests for SHS (Standing Hypothesis Set) storage."""
import json
from datetime import datetime, timezone

import pytest

from geopulse.run_output import SHSAction, SHSWriteback
from geopulse.shs import Hypothesis, SHSStorage


@pytest.fixture
def shs_dir(tmp_path):
    return tmp_path


@pytest.fixture
def storage(shs_dir):
    return SHSStorage(data_dir=shs_dir)


def _make_hypothesis(id: str = "h1", label: str = "有限冲突", **kwargs) -> Hypothesis:
    defaults = dict(
        id=id,
        label=label,
        statement="伊朗冲突将保持有限规模",
        confidence=0.6,
        horizon="W1_5",
        status="active",
    )
    defaults.update(kwargs)
    return Hypothesis(**defaults)


def test_load_empty(storage):
    assert storage.load() == []


def test_save_and_load(storage):
    hypotheses = [_make_hypothesis("h1"), _make_hypothesis("h2", "全面升级")]
    storage.save(hypotheses)
    loaded = storage.load()
    assert len(loaded) == 2
    assert loaded[0].id == "h1"
    assert loaded[1].id == "h2"


def test_save_creates_directory(tmp_path):
    nested = tmp_path / "deep" / "dir"
    storage = SHSStorage(data_dir=nested)
    storage.save([_make_hypothesis()])
    assert (nested / "shs.json").exists()


def test_roundtrip_preserves_fields(storage):
    h = _make_hypothesis(
        trigger_signals=["制裁升级"],
        invalidation_signals=["直接谈判启动"],
        observed_entities=["Iran", "US"],
        asset_expression="long oil vol",
    )
    storage.save([h])
    loaded = storage.load()[0]
    assert loaded.trigger_signals == ["制裁升级"]
    assert loaded.invalidation_signals == ["直接谈判启动"]
    assert loaded.asset_expression == "long oil vol"


def test_apply_writebacks_update(storage):
    storage.save([_make_hypothesis("h1", "有限冲突")])
    writebacks = [
        SHSWriteback(
            action=SHSAction.update,
            hypothesis_ref="h1",
            field_changed="confidence",
            old_value="0.6",
            new_value="0.75",
            trigger_reason="new evidence supports",
        )
    ]
    result = storage.apply_writebacks(writebacks, run_id="run_001")
    assert len(result) == 1
    assert result[0].confidence == 0.75
    assert "run_001" in result[0].source_run_ids


def test_apply_writebacks_add(storage):
    storage.save([])
    writebacks = [
        SHSWriteback(
            action=SHSAction.add,
            hypothesis_ref="h_new",
            field_changed="statement",
            new_value="新假设：谈判窗口打开",
            trigger_reason="new diplomatic signals",
        )
    ]
    result = storage.apply_writebacks(writebacks, run_id="run_002")
    assert len(result) == 1
    assert result[0].id == "h_new"
    assert result[0].statement == "新假设：谈判窗口打开"


def test_apply_writebacks_deprecate(storage):
    storage.save([_make_hypothesis("h1")])
    writebacks = [
        SHSWriteback(
            action=SHSAction.deprecate,
            hypothesis_ref="h1",
            field_changed="status",
            new_value="deprecated",
            trigger_reason="scenario invalidated",
        )
    ]
    result = storage.apply_writebacks(writebacks, run_id="run_003")
    assert result[0].status == "deprecated"


def test_apply_writebacks_by_label(storage):
    """Writebacks can reference hypotheses by label, not just id."""
    storage.save([_make_hypothesis("h1", "有限冲突")])
    writebacks = [
        SHSWriteback(
            action=SHSAction.update,
            hypothesis_ref="有限冲突",
            field_changed="confidence",
            old_value="0.6",
            new_value="0.8",
            trigger_reason="label-based update",
        )
    ]
    result = storage.apply_writebacks(writebacks, run_id="run_004")
    assert result[0].confidence == 0.8


def test_apply_writebacks_persists(storage):
    storage.save([_make_hypothesis("h1")])
    writebacks = [
        SHSWriteback(
            action=SHSAction.update,
            hypothesis_ref="h1",
            field_changed="confidence",
            old_value="0.6",
            new_value="0.9",
            trigger_reason="test",
        )
    ]
    storage.apply_writebacks(writebacks, run_id="run_005")
    # Reload from disk
    loaded = storage.load()
    assert loaded[0].confidence == 0.9
