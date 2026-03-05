"""End-to-end integration test with mocked LLM and Readwise."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from geopulse.pipeline import Pipeline


@pytest.fixture
def tmp_data(tmp_path):
    return tmp_path / "data"


class TestEndToEnd:
    def test_full_pipeline_e2e(self, tmp_data):
        pipeline = Pipeline(readwise_token="fake", anthropic_api_key="fake",
                            data_dir=tmp_data, proxy=None)

        mock_articles = [{
            "id": "1",
            "title": "Iran Begins Military Exercises Near Strait of Hormuz",
            "summary": "Iran's navy launched large-scale military exercises near the Strait of Hormuz, involving 20 warships and missile systems.",
            "source_url": "https://reuters.com/example",
            "tags": {"geopulse": {}},
            "category": "article",
        }]

        # Mock LLM event extraction response
        mock_events_response = MagicMock()
        mock_events_block = MagicMock()
        mock_events_block.text = json.dumps([{
            "headline": "伊朗在霍尔木兹海峡举行大规模军演",
            "details": "伊朗海军出动20艘军舰和导弹系统",
            "entities": ["伊朗", "霍尔木兹海峡"],
            "domains": ["军事"],
            "source_url": "https://reuters.com/example",
            "significance": 4,
        }], ensure_ascii=False)
        mock_events_response.content = [mock_events_block]

        # Mock LLM DAG update response
        mock_dag_response = MagicMock()
        mock_dag_block = MagicMock()
        mock_dag_block.text = json.dumps({
            "analysis": "伊朗军演显著提升海峡封锁风险",
            "model_insights": [
                {"model": "威慑理论", "insight": "军演是威慑信号，提升可信度"},
                {"model": "边缘策略", "insight": "当前处于升级阶梯中段"},
            ],
            "updates": {
                "new_nodes": [
                    {"id": "us_iran_conflict", "label": "美伊军事冲突", "domains": ["军事"],
                     "probability": 0.50, "confidence": 0.8, "evidence": ["baseline"], "reasoning": "根节点"},
                    {"id": "strait_closure", "label": "霍尔木兹海峡封锁", "domains": ["能源", "军事"],
                     "probability": 0.25, "confidence": 0.7, "evidence": ["伊朗军演涉及20艘军舰"], "reasoning": "军演提升封锁概率"},
                    {"id": "oil_surge", "label": "油价飙升", "domains": ["能源", "金融"],
                     "probability": 0.15, "confidence": 0.6, "evidence": ["海峡风险传导"], "reasoning": "封锁影响全球原油供应"},
                ],
                "new_edges": [
                    {"from": "us_iran_conflict", "to": "strait_closure", "weight": 0.7, "reasoning": "冲突导致封锁"},
                    {"from": "strait_closure", "to": "oil_surge", "weight": 0.8, "reasoning": "封锁影响油价"},
                ],
                "probability_changes": [],
                "removed_nodes": [],
                "removed_edges": [],
            },
        }, ensure_ascii=False)
        mock_dag_response.content = [mock_dag_block]

        with patch.object(pipeline.ingester, "fetch", return_value=mock_articles):
            # Mock the analyzer's Anthropic client
            pipeline.analyzer.client = MagicMock()
            pipeline.analyzer.client.messages.create.return_value = mock_events_response
            # Mock the DAG engine's Anthropic client
            pipeline.dag_engine.client = MagicMock()
            pipeline.dag_engine.client.messages.create.return_value = mock_dag_response

            report = pipeline.run()

        # Verify report
        assert report is not None
        assert "GeoPulse" in report
        assert "霍尔木兹" in report

        # Verify DAG was saved
        dag = pipeline.storage.load()
        assert dag is not None
        assert len(dag.nodes) == 3
        assert len(dag.edges) == 2

        # Verify propagation happened (oil_surge should have propagated probability > base 0.15)
        assert dag.nodes["oil_surge"].probability > 0.15

        # Verify orders
        orders = dag.compute_orders()
        assert orders["us_iran_conflict"] == 0
        assert orders["strait_closure"] == 1
        assert orders["oil_surge"] == 2

        # Verify events logged
        events_log = tmp_data / "events.jsonl"
        assert events_log.exists()
        lines = events_log.read_text().strip().split("\n")
        assert len(lines) == 1

        # Verify history snapshot
        assert len(pipeline.storage.list_history()) == 1
