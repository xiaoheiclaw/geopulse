"""Tests for Readwise ingester."""
from unittest.mock import MagicMock, patch
import pytest
from geopulse.ingester import ReadwiseIngester


class TestReadwiseIngester:
    def test_filter_by_tag(self):
        mock_docs = [
            {"id": "1", "title": "Iran test", "tags": {"geopulse": {}}, "summary": "test", "source_url": "http://a"},
            {"id": "2", "title": "Unrelated", "tags": {"other": {}}, "summary": "test", "source_url": "http://b"},
        ]
        ingester = ReadwiseIngester(token="fake", tag="geopulse", proxy=None)
        with patch.object(ingester, "_fetch_documents", return_value=mock_docs):
            articles = ingester.fetch()
        assert len(articles) == 1
        assert articles[0]["title"] == "Iran test"

    def test_empty_response(self):
        ingester = ReadwiseIngester(token="fake", tag="geopulse", proxy=None)
        with patch.object(ingester, "_fetch_documents", return_value=[]):
            articles = ingester.fetch()
        assert articles == []

    def test_article_structure(self):
        mock_docs = [
            {"id": "1", "title": "Test", "tags": {"geopulse": {}}, "summary": "content", "source_url": "http://a", "category": "article"},
        ]
        ingester = ReadwiseIngester(token="fake", tag="geopulse", proxy=None)
        with patch.object(ingester, "_fetch_documents", return_value=mock_docs):
            articles = ingester.fetch()
        assert "title" in articles[0]
        assert "summary" in articles[0]
        assert "source_url" in articles[0]
