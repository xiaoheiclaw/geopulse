"""Tests for DAG persistence."""
from pathlib import Path
import pytest
from geopulse.models import DAG, Edge, Node
from geopulse.storage import DAGStorage


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path / "data"

@pytest.fixture
def storage(tmp_data_dir):
    return DAGStorage(data_dir=tmp_data_dir)

@pytest.fixture
def sample_dag():
    return DAG(
        scenario="test", scenario_label="test",
        nodes={"a": Node(id="a", label="A", domains=["军事"],
                         probability=0.5, confidence=0.8,
                         evidence=["test"], reasoning="test")},
        edges=[],
    )


class TestDAGStorage:
    def test_save_and_load(self, storage, sample_dag):
        storage.save(sample_dag)
        loaded = storage.load()
        assert loaded is not None
        assert loaded.scenario == "test"
        assert len(loaded.nodes) == 1

    def test_load_returns_none_when_empty(self, storage):
        assert storage.load() is None

    def test_save_creates_history_snapshot(self, storage, sample_dag):
        storage.save(sample_dag)
        history = storage.list_history()
        assert len(history) == 1

    def test_increments_version(self, storage, sample_dag):
        storage.save(sample_dag)
        storage.save(sample_dag)
        loaded = storage.load()
        assert loaded.version == 2
        assert len(storage.list_history()) == 2

    def test_load_history_snapshot(self, storage, sample_dag):
        storage.save(sample_dag)
        snapshots = storage.list_history()
        loaded = storage.load_snapshot(snapshots[0])
        assert loaded.scenario == "test"
