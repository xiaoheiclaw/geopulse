"""Readwise Reader ingester for GeoPulse."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

READWISE_API_BASE = "https://readwise.io/api/v3"


GEOPULSE_SOURCES = {
    "Al Jazeera",
    "Reuters",
    "War on the Rocks",
    "OilPrice.com",
    "Responsible Statecraft",
    "The Cradle",
    "CSIS",
    "Iran International",
    "Energy Intelligence",
}


class ReadwiseIngester:
    """Fetch articles from Readwise Reader, filtered by source."""

    def __init__(
        self,
        token: str,
        tag: str = "geopulse",
        sources: set[str] | None = None,
        proxy: str | None = "http://127.0.0.1:7890",
        timeout: float = 30.0,
    ):
        self.token = token
        self.tag = tag
        self.sources = sources or GEOPULSE_SOURCES
        self.proxy = proxy
        self.timeout = timeout

    def fetch(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch documents and filter by source site_name or tag."""
        docs = self._fetch_documents(limit=limit)
        return [
            d for d in docs
            if d.get("site_name") in self.sources
            or self.tag in (d.get("tags") or {})
        ]

    def _fetch_documents(self, limit: int = 50) -> list[dict[str, Any]]:
        """Paginate through Readwise Reader /list/ endpoint."""
        all_docs: list[dict[str, Any]] = []
        cursor: str | None = None
        headers = {"Authorization": f"Token {self.token}"}

        with httpx.Client(proxy=self.proxy, timeout=self.timeout) as client:
            while len(all_docs) < limit:
                params: dict[str, Any] = {
                    "page_size": min(limit - len(all_docs), 100),
                    "location": "feed",
                }
                if cursor:
                    params["pageCursor"] = cursor

                resp = client.get(
                    f"{READWISE_API_BASE}/list/",
                    headers=headers,
                    params=params,
                )

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", "60"))
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                all_docs.extend(data.get("results", []))
                cursor = data.get("nextPageCursor")
                if not cursor:
                    break

        return all_docs
