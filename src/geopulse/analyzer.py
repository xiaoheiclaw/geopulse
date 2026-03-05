"""LLM-based event extraction from news articles."""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from .models import Event

ANALYZER_SYSTEM_PROMPT = """\
你是一个新闻事件提取器。从以下文章中提取与"美伊冲突"相关的结构化事件。

如果文章与美伊冲突无关，返回空 JSON 列表 []。
如果是纯情绪/标题党/没有实质信息，返回空列表 []。

每个事件输出为 JSON 数组中的对象：
[
  {
    "headline": "事件一句话描述（≤30字）",
    "details": "关键细节（≤100字）",
    "entities": ["相关实体"],
    "domains": ["影响的领域：军事/能源/经济/科技/金融/政治/社会"],
    "source_url": "原文URL",
    "significance": 1-5
  }
]

评分标准：5=重大转折 4=显著影响 3=值得关注 2=轻微 1=噪音
"""


class EventAnalyzer:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        proxy: str | None = "http://127.0.0.1:7890",
    ):
        self.model = model
        http_client = None
        if proxy:
            import httpx

            http_client = httpx.Client(proxy=proxy)
        self.client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

    def analyze(self, article: dict[str, Any]) -> list[Event]:
        """Extract geopolitical events from an article via LLM.

        Returns a list of Event objects. Returns empty list on any error
        (malformed output, API failure, irrelevant content).
        """
        try:
            raw_events = self._call_llm(article)
        except Exception:
            return []

        events: list[Event] = []
        for ev in raw_events:
            try:
                events.append(Event(
                    headline=ev["headline"],
                    details=ev.get("details", ""),
                    entities=ev.get("entities", []),
                    domains=ev.get("domains", []),
                    source_url=ev.get("source_url", article.get("source_url", "")),
                    significance=ev.get("significance", 3),
                ))
            except Exception:
                continue
        return events

    def _call_llm(self, article: dict[str, Any]) -> list[dict]:
        """Send article to Claude and parse structured event JSON."""
        user_prompt = (
            f"文章标题：{article.get('title', '')}\n\n"
            f"文章内容：\n{(article.get('summary', '') or article.get('content', ''))[:3000]}\n\n"
            f"来源：{article.get('source_url', '')}"
        )
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.2,
            system=ANALYZER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return self._parse_json_array(text)

    @staticmethod
    def _parse_json_array(text: str) -> list[dict]:
        """Extract a JSON array from LLM output, handling markdown fences."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                inner = parts[1].strip()
                if inner.lower().startswith("json"):
                    inner = inner[4:].strip()
                text = inner
        # Find the JSON array in the text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
