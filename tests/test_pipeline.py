"""Tests for pipeline orchestration."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from geopulse.models import DAG, Event, Node
from geopulse.pipeline import Pipeline


@pytest.fixture
def tmp_data(tmp_path):
    return tmp_path / "data"


class TestPipeline:
    def test_run_creates_dag_on_first_run(self, tmp_data):
        pipeline = Pipeline(
            readwise_token="fake",
            anthropic_api_key="fake",
            data_dir=tmp_data,
            proxy=None,
        )
        mock_articles = [
            {
                "title": "Iran test",
                "summary": "test content",
                "source_url": "http://a",
                "tags": {"geopulse": {}},
            }
        ]
        mock_events = [Event(headline="测试事件", domains=["军事"], significance=3)]
        mock_dag = DAG(
            scenario="us_iran_conflict",
            scenario_label="美伊冲突",
            nodes={
                "test": Node(
                    id="test",
                    label="测试",
                    domains=["军事"],
                    probability=0.5,
                    confidence=0.8,
                    evidence=["test"],
                    reasoning="test",
                )
            },
            edges=[],
        )

        with (
            patch.object(pipeline.ingester, "fetch", return_value=mock_articles),
            patch.object(pipeline.analyzer, "analyze", return_value=mock_events),
            patch.object(pipeline.dag_engine, "update", return_value=mock_dag),
        ):
            report = pipeline.run()

        assert report is not None
        assert "GeoPulse" in report
        assert pipeline.storage.load() is not None

    def test_run_with_no_articles(self, tmp_data):
        pipeline = Pipeline(
            readwise_token="fake",
            anthropic_api_key="fake",
            data_dir=tmp_data,
            proxy=None,
        )
        with patch.object(pipeline.ingester, "fetch", return_value=[]):
            report = pipeline.run()
        assert report is None
