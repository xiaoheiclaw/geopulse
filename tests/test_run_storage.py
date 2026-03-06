"""Tests for RunOutput archival storage."""
import json
from pathlib import Path

import pytest

from geopulse.run_output import RunOutput
from geopulse.run_storage import RunOutputStorage

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_run_output.json"


@pytest.fixture
def sample_output() -> RunOutput:
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    return RunOutput.model_validate_json(raw)


@pytest.fixture
def storage(tmp_path) -> RunOutputStorage:
    return RunOutputStorage(data_dir=tmp_path)


def test_save_creates_file(storage, sample_output):
    path = storage.save(sample_output)
    assert path.exists()
    assert path.name == "run_20260306T120000Z.json"


def test_load_existing(storage, sample_output):
    storage.save(sample_output)
    loaded = storage.load("run_20260306T120000Z")
    assert loaded is not None
    assert loaded.meta.run_id == "run_20260306T120000Z"
    assert loaded.meta.evidence_count == 3


def test_load_nonexistent(storage):
    assert storage.load("nonexistent") is None


def test_list_runs_empty(storage):
    assert storage.list_runs() == []


def test_list_runs_ordering(storage, sample_output):
    import time
    # Save two runs
    storage.save(sample_output)
    time.sleep(0.01)
    # Modify run_id and save again
    second = sample_output.model_copy(deep=True)
    second.meta.run_id = "run_20260306T130000Z"
    storage.save(second)
    runs = storage.list_runs()
    assert len(runs) == 2
    assert runs[0] == "run_20260306T130000Z"  # newest first


def test_latest(storage, sample_output):
    storage.save(sample_output)
    latest = storage.latest()
    assert latest is not None
    assert latest.meta.run_id == sample_output.meta.run_id


def test_latest_empty(storage):
    assert storage.latest() is None


def test_list_runs_limit(storage, sample_output):
    for i in range(5):
        copy = sample_output.model_copy(deep=True)
        copy.meta.run_id = f"run_{i:03d}"
        storage.save(copy)
    runs = storage.list_runs(limit=3)
    assert len(runs) == 3
