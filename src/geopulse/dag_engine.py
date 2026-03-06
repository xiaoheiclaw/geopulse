"""DAG Engine: LLM-driven updates to the causal probability network."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import anthropic

from .mental_models import build_prompt_injection
from .models import DAG, Edge, Event, Node

ALL_DOMAINS = ["军事", "能源", "经济", "科技", "金融", "政治", "社会"]

DOMAIN_SYSTEM_PROMPT = """\
你是一个地缘政治风险分析师，当前从**{domain}**视角分析事件对因果概率网络（DAG）的影响。

## 你的分析工具箱（{domain}相关思维模型）
{mental_models}

## 分析视角
你当前专注于 **{domain}** 维度。请：
1. 识别事件中与{domain}直接相关的因果链
2. 提出{domain}领域的预测节点（尚未发生但可能发生的后果）
3. 建立从事实节点到{domain}预测节点的因果边
4. 也可以建立跨领域的因果边（如军事→能源），但主要聚焦{domain}

## 节点类型
- **事实节点**：已发生的事件，概率接近 1.0
- **预测节点**：尚未发生但可能发生的后果，概率反映你的判断
预测节点才是 DAG 的核心价值。概率应有区分度，不要全部集中在 0.8-1.0。

## 阶数
- 0阶=触发事件，1阶=直接后果，2阶=间接传导，3阶+=深层连锁

## 规则
1. 概率范围 0.0-1.0，保留两位小数
2. DAG 必须无环
3. 每个节点归属 1-2 个领域
4. 每条边必须有 reasoning
5. 概率变化必须有 evidence 支撑
6. 至少提出 2-3 个{domain}领域的预测节点
7. 如果事件与{domain}完全无关，输出空更新

## 输出格式（严格 JSON，无 markdown 代码块）
{{
  "domain": "{domain}",
  "analysis": "{domain}视角分析摘要（150字内）",
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
    """Drives DAG updates by calling an LLM per domain and merging results."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        proxy: str | None = "http://127.0.0.1:7890",
        base_url: str | None = None,
    ):
        self.model = model
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if proxy:
            import httpx

            kwargs["http_client"] = httpx.Client(proxy=proxy)
        self.client = anthropic.Anthropic(**kwargs)

    def update(self, dag: DAG, events: list[Event]) -> DAG:
        """Process events by analyzing each relevant domain separately, then merge."""
        if not events:
            return dag

        # Determine which domains are touched by these events
        active_domains = self._active_domains(events, dag)
        print(f"  Active domains: {', '.join(active_domains)}")

        result = dag.model_copy(deep=True)
        all_analyses: list[str] = []
        all_insights: list[dict] = []

        for domain in active_domains:
            print(f"  Analyzing [{domain}]...")
            try:
                llm_output = self._call_llm_for_domain(result, events, domain)
                result = self._apply_updates(result, llm_output)
                analysis = llm_output.get("analysis", "")
                if analysis:
                    all_analyses.append(f"【{domain}】{analysis}")
                all_insights.extend(llm_output.get("model_insights", []))
                n_new = len(llm_output.get("updates", {}).get("new_nodes", []))
                n_edges = len(llm_output.get("updates", {}).get("new_edges", []))
                print(f"    +{n_new} nodes, +{n_edges} edges")
            except Exception as e:
                print(f"    ERROR: {e}")

        # Store combined metadata
        object.__setattr__(result, "_analysis", "\n".join(all_analyses))
        object.__setattr__(result, "_model_insights", all_insights)

        return result

    def _active_domains(self, events: list[Event], dag: DAG) -> list[str]:
        """Determine which domains need analysis based on events and existing DAG."""
        touched: set[str] = set()
        for ev in events:
            touched.update(ev.domains)
        for node in dag.nodes.values():
            touched.update(node.domains)
        # Return in canonical order, only domains that are touched
        if not touched:
            return ALL_DOMAINS
        return [d for d in ALL_DOMAINS if d in touched]

    def _call_llm_for_domain(
        self, dag: DAG, events: list[Event], domain: str, retries: int = 2
    ) -> dict[str, Any]:
        """Call the LLM for a specific domain perspective."""
        mental_models = build_prompt_injection(domains=[domain])
        system = DOMAIN_SYSTEM_PROMPT.replace("{domain}", domain).replace(
            "{mental_models}", mental_models
        )
        events_json = [e.model_dump(mode="json") for e in events]
        user_prompt = (
            f"## 当前 DAG 状态\n```json\n{dag.to_json()}\n```\n\n"
            f"## 新接收到的事件\n```json\n"
            f"{json.dumps(events_json, ensure_ascii=False, indent=2)}\n```"
        )
        last_err: Exception | None = None
        for attempt in range(1 + retries):
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.2,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            try:
                return self._parse_json(text)
            except (json.JSONDecodeError, Exception) as e:
                last_err = e
                if attempt < retries:
                    import time

                    time.sleep(1)
                    continue
        raise last_err  # type: ignore[misc]

    def _apply_updates(self, dag: DAG, output: dict[str, Any]) -> DAG:
        """Apply LLM-generated updates to the DAG, rejecting cycles."""
        result = dag.model_copy(deep=True)
        updates = output.get("updates", {})
        now = datetime.now(timezone.utc)

        # Add new nodes (skip if already exists — earlier domain analysis wins)
        for nd in updates.get("new_nodes", []):
            nid = nd["id"]
            if nid in result.nodes:
                continue
            node = Node(
                id=nid,
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
        existing_edges = {(e.source, e.target) for e in result.edges}
        for ed in updates.get("new_edges", []):
            source = ed.get("from", ed.get("source", ""))
            target = ed.get("to", ed.get("target", ""))
            if source not in result.nodes or target not in result.nodes:
                continue
            if (source, target) in existing_edges:
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
            else:
                existing_edges.add((source, target))

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
            raw = match.group(0)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
            # Attempt to fix common LLM JSON issues:
            # 1. Trailing commas before } or ]
            fixed = re.sub(r",\s*([}\]])", r"\1", raw)
            # 2. Single quotes -> double quotes (only outside strings)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            # 3. Try truncating to last valid closing brace
            depth = 0
            last_valid = -1
            for i, ch in enumerate(fixed):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        last_valid = i
                        break
            if last_valid > 0:
                try:
                    return json.loads(fixed[: last_valid + 1])
                except json.JSONDecodeError:
                    pass
            raise
        return json.loads(text)
