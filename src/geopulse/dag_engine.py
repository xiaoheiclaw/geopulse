"""DAG Engine: LLM-driven updates to the causal probability network."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from .mental_models import build_prompt_injection
from .models import DAG, Edge, Event, Node

DAG_ENGINE_SYSTEM_PROMPT = """\
你是一个地缘政治风险分析师，负责维护一个因果概率网络（DAG）。

## 你的分析工具箱（思维模型）
{mental_models}

## 规则
1. 概率范围 0.0-1.0，保留两位小数
2. DAG 必须无环（不允许循环因果）
3. 每个新节点必须指定 domains（可选：军事/能源/经济/科技/金融/政治/社会）
4. 每条边必须有 reasoning 解释因果关系
5. 概率变化必须有 evidence 支撑
6. 只在有充分理由时才新增节点，避免网络过度膨胀
7. 如果事件不影响任何现有节点且不值得新增节点，输出空更新

## 输出格式（严格 JSON，无 markdown 代码块）
{{
  "analysis": "整体分析摘要（200字内）",
  "model_insights": [
    {{ "model": "模型名", "insight": "该模型视角下的洞察" }}
  ],
  "updates": {{
    "new_nodes": [
      {{
        "id": "snake_case_id",
        "label": "中文标签",
        "domains": ["领域"],
        "probability": 0.5,
        "confidence": 0.7,
        "evidence": ["证据"],
        "reasoning": "为什么新增"
      }}
    ],
    "new_edges": [
      {{ "from": "source_id", "to": "target_id", "weight": 0.7, "reasoning": "因果解释" }}
    ],
    "probability_changes": [
      {{
        "node_id": "id",
        "new_probability": 0.6,
        "new_confidence": 0.8,
        "evidence": ["新证据"],
        "reasoning": "调整原因"
      }}
    ],
    "removed_nodes": [],
    "removed_edges": []
  }}
}}
"""


class DAGEngine:
    """Drives DAG updates by calling an LLM and applying structured changes."""

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

    def update(self, dag: DAG, events: list[Event]) -> DAG:
        """Process events and return updated DAG."""
        if not events:
            return dag
        llm_output = self._call_llm(dag, events)
        return self._apply_updates(dag, llm_output)

    def _call_llm(self, dag: DAG, events: list[Event]) -> dict[str, Any]:
        """Call the LLM with current DAG state and new events."""
        mental_models = build_prompt_injection()
        system = DAG_ENGINE_SYSTEM_PROMPT.replace("{mental_models}", mental_models)
        events_json = [e.model_dump(mode="json") for e in events]
        user_prompt = (
            f"## 当前 DAG 状态\n```json\n{dag.to_json()}\n```\n\n"
            f"## 新接收到的事件\n```json\n"
            f"{json.dumps(events_json, ensure_ascii=False, indent=2)}\n```"
        )
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.3,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return self._parse_json(text)

    def _apply_updates(self, dag: DAG, output: dict[str, Any]) -> DAG:
        """Apply LLM-generated updates to the DAG, rejecting cycles."""
        result = dag.model_copy(deep=True)
        updates = output.get("updates", {})
        now = datetime.now(timezone.utc)

        # Store analysis metadata on the DAG instance for downstream reporting.
        # Using object.__setattr__ since Pydantic models restrict direct assignment.
        object.__setattr__(result, "_analysis", output.get("analysis", ""))
        object.__setattr__(result, "_model_insights", output.get("model_insights", []))

        # Add new nodes
        for nd in updates.get("new_nodes", []):
            node = Node(
                id=nd["id"],
                label=nd["label"],
                domains=nd.get("domains", []),
                probability=max(0.0, min(1.0, nd.get("probability", 0.5))),
                confidence=max(0.0, min(1.0, nd.get("confidence", 0.5))),
                evidence=nd.get("evidence", []),
                reasoning=nd.get("reasoning", ""),
                last_updated=now,
                created=now,
            )
            result.nodes[node.id] = node

        # Add new edges with per-edge cycle check
        for ed in updates.get("new_edges", []):
            source = ed.get("from", ed.get("source", ""))
            target = ed.get("to", ed.get("target", ""))
            if source not in result.nodes or target not in result.nodes:
                continue
            edge = Edge(
                source=source,
                target=target,
                weight=max(0.0, min(1.0, ed.get("weight", 0.5))),
                reasoning=ed.get("reasoning", ""),
            )
            result.edges.append(edge)
            if result.has_cycle():
                result.edges.pop()

        # Apply probability changes
        for ch in updates.get("probability_changes", []):
            nid = ch["node_id"]
            if nid in result.nodes:
                node = result.nodes[nid]
                node.probability = max(0.0, min(1.0, ch["new_probability"]))
                node.confidence = max(
                    0.0, min(1.0, ch.get("new_confidence", node.confidence))
                )
                node.evidence.extend(ch.get("evidence", []))
                node.reasoning = ch.get("reasoning", node.reasoning)
                node.last_updated = now

        # Remove nodes and their connected edges
        for nid in updates.get("removed_nodes", []):
            result.nodes.pop(nid, None)
            result.edges = [
                e for e in result.edges if e.source != nid and e.target != nid
            ]

        # Remove specific edges
        for es in updates.get("removed_edges", []):
            src = es.get("from", es.get("source", ""))
            tgt = es.get("to", es.get("target", ""))
            result.edges = [
                e
                for e in result.edges
                if not (e.source == src and e.target == tgt)
            ]

        return result

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                inner = parts[1].strip()
                if inner.lower().startswith("json"):
                    inner = inner[4:].strip()
                text = inner
        # Find the outermost JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
