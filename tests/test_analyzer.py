"""Tests for LLM event analyzer."""
import json
from unittest.mock import MagicMock, patch

import pytest

from geopulse.analyzer import EventAnalyzer
from geopulse.models import Event


class TestEventAnalyzer:
    def _mock_llm_response(self, events_json: list[dict]) -> MagicMock:
        mock_resp = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps(events_json, ensure_ascii=False)
        mock_resp.content = [mock_block]
        return mock_resp

    def test_extracts_events(self):
        analyzer = EventAnalyzer(api_key="fake")
        mock_events = [{
            "headline": "伊朗宣布恢复高浓度铀浓缩",
            "details": "伊朗原子能组织宣布将浓缩铀纯度提升至60%",
            "entities": ["伊朗", "IAEA"],
            "domains": ["军事", "政治"],
            "source_url": "http://example.com",
            "significance": 4,
        }]
        with patch.object(analyzer, "_call_llm", return_value=mock_events):
            events = analyzer.analyze({
                "title": "Iran resumes enrichment",
                "summary": "Iran announces 60% enrichment",
                "source_url": "http://example.com",
            })
        assert len(events) == 1
        assert isinstance(events[0], Event)
        assert events[0].significance == 4

    def test_filters_irrelevant(self):
        analyzer = EventAnalyzer(api_key="fake")
        with patch.object(analyzer, "_call_llm", return_value=[]):
            events = analyzer.analyze({
                "title": "Apple releases new iPhone",
                "summary": "Tech product launch",
                "source_url": "http://example.com",
            })
        assert events == []

    def test_handles_malformed_llm_output(self):
        analyzer = EventAnalyzer(api_key="fake")
        with patch.object(analyzer, "_call_llm", side_effect=ValueError("bad json")):
            events = analyzer.analyze({
                "title": "test",
                "summary": "test",
                "source_url": "http://example.com",
            })
        assert events == []
