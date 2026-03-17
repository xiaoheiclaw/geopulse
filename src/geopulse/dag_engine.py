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

## 节点类型与概率语义
三种节点类型，概率含义不同：
- **event（事件节点）**：离散已发生事件。prob = 发生了吗？（1.0=确认，0=未发生）
- **state（状态节点）**：持续性条件。prob = 未来30天内该状态持续的概率
- **prediction（预测节点）**：未来事件。prob = 在指定时间窗口(time_horizon)内发生的概率

新建节点时**必须指定 node_type 和 time_horizon**（state/prediction必填）。

## ⚠️ 强制4阶推演规则（CRITICAL）
**每一个新事件或概率变化，必须沿因果链推演至少4阶。1-2阶分析是不合格的。**

推演模板：
```
触发 →[物理因果, 时间尺度]→ 1阶后果
  →[市场/政策反应, 时间尺度]→ 2阶后果
    →[反应的反应/二阶博弈, 时间尺度]→ 3阶后果
      →[结构性变化/均衡移动, 时间尺度]→ 4阶后果
```

每一阶要求：
1. 明确的**传导机制**（不是"导致"，而是"通过X机制导致"）
2. **时间尺度**（天/周/月/季度）
3. **放大器和抑制器**（什么会加速/延缓这个传导）

常见的跨领域传导链（不要遗漏）：
- 能源价格 → 石脑油/乙烯 → 化肥 → 粮食 → 社会动荡 → 政权稳定
- 军事行动 → 航运中断 → 保险撤离 → 贸易量下降 → 港口经济
- 油价 → 汽油零售价 → 消费者信心 → 选举政治 → 战争决策（反馈回路）
- 金融价格 → 企业决策 → 就业 → 社会稳定
- 央行困境 → 流动性紧缩 → 信贷收缩 → EM资本外逃 → 主权危机

**自检：如果你的分析在2阶就停了，问自己——第3阶真的没有吗？还是我偷懒了？**

## 阶数
- 0阶=触发事件，1阶=直接后果，2阶=间接传导，3阶=深层连锁，4阶=结构性重定价

## 规则
1. 概率范围 0.0-1.0，保留两位小数
2. DAG 必须无环
3. 每个节点归属 1-2 个领域
4. 每条边必须有 reasoning，包含传导机制和时间尺度
5. 概率变化必须有 evidence 支撑
6. **全量评估责任**：你负责掌控{domain}领域下**所有节点**的升降。如果新事件降低了某些风险，你必须在 `probability_changes` 中显式下调这些概率。
7. **传导逻辑**：系统会自动进行数学传导，但你的显式判断具有最高优先级。
8. 至少提出 2-3 个{domain}领域的预测节点，其中至少1个是3阶或以上
9. 如果事件与{domain}完全无关，输出空更新
10. **反馈回路**：如果发现A→B→...→A的回路，标注为反馈回路并说明是正反馈（放大）还是负反馈（抑制）
11. **跨领域传导**：优先建立跨越2个以上领域的传导链（如军事→能源→化工→农业→社会）

## 输出格式（严格 JSON，无 markdown 代码块）
⚠️ 直接输出 JSON 对象，不要在 JSON 前后写任何分析文字或解释。整个回复必须是一个合法的 JSON 对象。
{{
  "domain": "{domain}",
  "analysis": "{domain}视角分析摘要（150字内）",
  "causal_chains": [
    "触发A →[机制, 周]→ 1阶B →[机制, 月]→ 2阶C →[机制, 季]→ 3阶D →[机制, 年]→ 4阶E"
  ],
  "model_insights": [
    {{ "model": "模型名", "insight": "该模型视角下的洞察" }}
  ],
  "updates": {{
    "new_nodes": [
      {{
        "id": "snake_case_id",
        "label": "中文标签",
        "node_type": "event|state|prediction",
        "time_horizon": "30d|60d|90d|180d",
        "domains": ["领域"],
        "probability": 0.5,
        "confidence": 0.7,
        "evidence": ["证据"],
        "reasoning": "为什么新增。状态节点说明30天持续概率，预测节点说明时间窗口内发生概率。"
      }}
    ],
    "new_edges": [
      {{ "from": "source_id", "to": "target_id", "weight": 0.7, "reasoning": "因果机制 + 时间尺度" }}
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

            kwargs["http_client"] = httpx.Client(proxy=proxy, timeout=300.0)
        kwargs["timeout"] = 300.0
        self.client = anthropic.Anthropic(**kwargs)

    def update(self, dag: DAG, events: list[Event]) -> DAG:
        """Process events by analyzing each relevant domain separately, then merge."""
        if not events:
            return dag

        # v3.1: classify events as action vs rhetoric before processing
        actions, rhetoric = self._classify_events(events)
        print(f"  Event filter: {len(actions)} actions, {len(rhetoric)} rhetoric (skipped)")

        if not actions:
            print("  No action events to process, skipping DAG update")
            return dag

        # Determine which domains are touched by action events only
        active_domains = self._active_domains(actions, dag)
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

    def _classify_events(self, events: list[Event]) -> tuple[list[Event], list[Event]]:
        """Classify events as action (→ DAG update) vs rhetoric (→ log only).
        
        v3.1 noise filter: words vs actions, not person-based.
        Uses LLM for semantic classification since keyword matching can't
        distinguish "Trump orders strike" from "Trump warns of strike".
        """
        if len(events) <= 3:
            # Small batch: classify inline with a quick LLM call
            return self._classify_events_llm(events)
        
        # Large batch: use heuristic pre-filter then LLM for ambiguous cases
        actions: list[Event] = []
        rhetoric: list[Event] = []
        ambiguous: list[Event] = []
        
        # Strong action indicators (high precision)
        action_patterns = [
            "struck", "bombed", "launched", "deployed", "ordered",
            "signed", "released", "intercepted", "killed", "seized",
            "sank", "shot down", "invaded", "blockaded", "mined",
            "confirmed", "collapsed", "surged past", "breached",
            "hit $", "fell below", "evacuated", "closed",
            "strikes", "shoots down", "releases", "surges past",
            "rose to", "dropped to", "climbed to", "plunged",
            "broke through", "topped", "crashed",
        ]
        # Strong rhetoric indicators (high precision)
        rhetoric_patterns = [
            "says", "warns", "threatens", "vows", "calls for",
            "predicts", "forecasts", "analysts say", "sources say",
            "could", "may", "might", "considering", "mulling",
            "urges", "demands", "condemns", "slams", "blasts",
            "opinion", "editorial", "analysis:",
        ]
        
        for ev in events:
            text = (getattr(ev, 'headline', '') or str(ev)).lower()
            
            action_score = sum(1 for p in action_patterns if p in text)
            rhetoric_score = sum(1 for p in rhetoric_patterns if p in text)
            
            if action_score > 0 and rhetoric_score == 0:
                actions.append(ev)
            elif rhetoric_score > 0 and action_score == 0:
                rhetoric.append(ev)
            else:
                ambiguous.append(ev)
        
        # Classify ambiguous events with LLM if any
        if ambiguous:
            llm_actions, llm_rhetoric = self._classify_events_llm(ambiguous)
            actions.extend(llm_actions)
            rhetoric.extend(llm_rhetoric)
        
        return actions, rhetoric

    def _classify_events_llm(self, events: list[Event]) -> tuple[list[Event], list[Event]]:
        """Use LLM to classify events as action vs rhetoric."""
        try:
            headlines = []
            for i, ev in enumerate(events):
                h = getattr(ev, 'headline', None) or str(ev)
                headlines.append(f"{i}: {h[:120]}")
            
            prompt = (
                "对以下新闻事件分类。输出JSON: {\"actions\": [序号], \"rhetoric\": [序号]}\n"
                "分类规则:\n"
                "- action: 实际发生的事(打击/部署/签署/释放/价格变动/人员伤亡/设施损毁)\n"
                "- rhetoric: 言辞/声明/威胁/预测/分析/呼吁(未转化为行动)\n"
                "- 同一事件含action就算action\n\n"
                + "\n".join(headlines)
            )
            
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            result = self._parse_json(text)
            
            action_ids = set(result.get("actions", []))
            actions = [events[i] for i in range(len(events)) if i in action_ids]
            rhetoric = [events[i] for i in range(len(events)) if i not in action_ids]
            return actions, rhetoric
        except Exception as e:
            print(f"    [classify] LLM failed ({e}), treating all as actions")
            return events, []

    def _compact_dag_json(self, dag: DAG) -> str:
        """Return an ultra-compact JSON representation of the DAG for smaller prompts."""
        compact_nodes = {}
        for nid, n in dag.nodes.items():
            compact_nodes[nid] = [n.label, round(n.probability, 2), n.domains]
        compact_edges = [[e.source, e.target, round(e.weight, 2)] for e in dag.edges]
        return json.dumps({"n": compact_nodes, "e": compact_edges, "v": dag.version}, ensure_ascii=False)

    def _call_llm_for_domain(
        self, dag: DAG, events: list[Event], domain: str, retries: int = 2
    ) -> dict[str, Any]:
        """Call the LLM for a specific domain perspective."""
        mental_models = build_prompt_injection(domains=[domain])
        system = DOMAIN_SYSTEM_PROMPT_MINI.replace("{domain}", domain)
        events_json = [e.model_dump(mode="json") for e in events]
        # Use compact system prompt to avoid relay timeouts
        system = (
            f"你是地缘政治风险分析师，从**{domain}**视角分析事件对DAG的影响。"
            f"规则：概率0.0-1.0；DAG无环；每条边有reasoning含传导机制+时间尺度；推演至少4阶。"
            f"直接输出JSON（无markdown fence），格式："
            "{"
            f"\"domain\":\"{domain}\","
            "\"analysis\":\"150字内摘要\","
            "\"causal_chains\":[\"A→B→C→D\"],"
            "\"updates\":{"
            "\"new_nodes\":[{\"id\":\"snake_case\",\"label\":\"中文\",\"node_type\":\"event|state|prediction\","
            "\"time_horizon\":\"30d\",\"domains\":[\"领域\"],\"probability\":0.5,\"confidence\":0.7,"
            "\"evidence\":[\"证据\"],\"reasoning\":\"原因\"}],"
            "\"new_edges\":[{\"from\":\"src\",\"to\":\"tgt\",\"weight\":0.7,\"reasoning\":\"机制+时间\"}],"
            "\"probability_changes\":[{\"node_id\":\"id\",\"new_probability\":0.6,\"new_confidence\":0.8,"
            "\"evidence\":[\"证据\"],\"reasoning\":\"原因\"}],"
            "\"removed_nodes\":[],\"removed_edges\":[]"
            "}}"
        )
        compact_dag = self._compact_dag_json(dag)
        user_prompt = (
            f"DAG状态:\n{compact_dag}\n\n"
            f"新事件:\n{json.dumps(events_json, ensure_ascii=False)}\n\n"
            f"只输出JSON对象。"
        )
        last_err: Exception | None = None
        for attempt in range(1 + retries):
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
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

        # Sync to graph database
        self._sync_to_graph_db(result, events)

        return result

    def _sync_to_graph_db(self, dag: DAG, events: list[Event]):
        """Sync DAG updates and events to the graph database."""
        try:
            from .graph_db import GeoPulseGraph
            import sqlite3

            g = GeoPulseGraph(str(self.data_dir))
            # Reload graph from the updated DAG object (in-memory)
            g.G.clear()
            for nid, node in dag.nodes.items():
                g.G.add_node(nid, **{
                    "label": node.label,
                    "probability": node.probability,
                    "confidence": node.confidence,
                    "domains": node.domains,
                    "evidence": node.evidence,
                    "reasoning": node.reasoning,
                })
            for edge in dag.edges:
                g.G.add_edge(edge.source, edge.target,
                             weight=edge.weight, reasoning=edge.reasoning)

            # Insert new events
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(g.db_path) as conn:
                for ev in events:
                    conn.execute(
                        """INSERT INTO events (headline, details, source_url, source_name,
                           domains, significance, timestamp, logged_at, backfilled)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                        (
                            ev.headline[:200] if hasattr(ev, 'headline') else str(ev)[:200],
                            getattr(ev, 'details', ''),
                            getattr(ev, 'source_url', ''),
                            getattr(ev, 'source_name', ''),
                            json.dumps(ev.domains, ensure_ascii=False),
                            getattr(ev, 'significance', 3),
                            now[:10],
                            now,
                        ),
                    )

                # Snapshot node probabilities for time series
                version = dag.version
                for nid, node in dag.nodes.items():
                    conn.execute(
                        """INSERT OR REPLACE INTO node_history
                           (node_id, timestamp, probability, confidence, dag_version)
                           VALUES (?, ?, ?, ?, ?)""",
                        (nid, now, node.probability, node.confidence, version),
                    )

            # Re-link new events to nodes
            g.auto_link_events()
            print(f"    [graph_db] synced {len(events)} events + {len(dag.nodes)} node snapshots")
        except Exception as e:
            print(f"    [graph_db] sync failed (non-fatal): {e}")

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
            raise json.JSONDecodeError(
                f"Could not parse JSON from LLM output (len={len(text)})",
                text[:200],
                0,
            )
        # No matched {..} pair — likely truncated JSON. Try to repair.
        first_brace = text.find("{")
        if first_brace >= 0:
            fragment = text[first_brace:]
            # Remove trailing partial string/key (cut at last complete value)
            # Find the last comma or colon, then truncate there
            repaired = re.sub(r'[,\s]*"[^"]*$', "", fragment)  # drop trailing partial string
            repaired = re.sub(r",\s*$", "", repaired)  # drop trailing comma
            # Close all open brackets/braces
            open_braces = repaired.count("{") - repaired.count("}")
            open_brackets = repaired.count("[") - repaired.count("]")
            repaired += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        return json.loads(text)

# Minimal system prompt for faster API calls
DOMAIN_SYSTEM_PROMPT_MINI = """\
地缘政治{domain}视角分析师。从DAG和事件中识别因果链并更新概率。
输出格式(直接JSON，无其他文字)：
{{"domain":"{domain}","analysis":"50字摘要","updates":{{"probability_changes":[{{"node_id":"id","new_probability":0.5,"reasoning":"原因"}}],"new_nodes":[],"new_edges":[]}}}}
"""
