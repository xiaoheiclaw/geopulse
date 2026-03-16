"""Structural verification — replaces Brier-score calibration for n=1 crises.

Four feedback mechanisms:
1. Omission detection: events that happened but have no DAG node
2. Stale node detection: nodes not updated despite new evidence
3. Causal chain verification: did transmission chains play out?
4. Noise reclassification audit: words vs actions, not person-based
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import networkx as nx


class StructuralVerifier:
    """Structural feedback for the DAG — what's missing matters more than what's wrong."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.dag = self._load_dag()
        self.db_path = self.data_dir / "geopulse.db"

    def _load_dag(self) -> dict:
        with open(self.data_dir / "dag.json") as f:
            return json.load(f)

    # ── 1. Omission Detection ──────────────────────────────

    def detect_omissions(self, days: int = 3, min_significance: int = 4) -> list[dict]:
        """Find high-significance events that don't match any DAG node.
        
        These are more important than probability errors — they're structural blind spots.
        """
        if not self.db_path.exists():
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()[:10]

        with sqlite3.connect(self.db_path) as conn:
            # Events with NO or LOW node links
            rows = conn.execute("""
                SELECT e.id, e.headline, e.significance, e.timestamp,
                       COUNT(l.node_id) as link_count,
                       MAX(l.relevance) as max_relevance
                FROM events e
                LEFT JOIN event_node_links l ON e.id = l.event_id
                WHERE e.significance >= ?
                  AND e.timestamp >= ?
                GROUP BY e.id
                HAVING link_count = 0 OR max_relevance < 0.15
                ORDER BY e.significance DESC, e.timestamp DESC
                LIMIT 20
            """, (min_significance, cutoff)).fetchall()

        omissions = []
        for eid, headline, sig, ts, links, rel in rows:
            omissions.append({
                "event_id": eid,
                "headline": headline,
                "significance": sig,
                "timestamp": ts,
                "node_links": links,
                "max_relevance": rel or 0,
                "action": "NEED_NODE — 高显著度事件无对应 DAG 节点",
            })
        return omissions

    # ── 2. Stale Node Detection ────────────────────────────

    def detect_stale_nodes(self, stale_days: int = 3) -> list[dict]:
        """Find nodes whose probability hasn't changed despite new events.
        
        Either genuinely stable, or we're not processing new evidence properly.
        """
        nodes = self.dag.get("nodes", {})
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=stale_days)).isoformat()
        stale = []

        for nid, node in nodes.items():
            last_updated = node.get("last_updated", "")
            if not last_updated:
                stale.append({
                    "node_id": nid,
                    "label": node.get("label", nid),
                    "probability": node.get("probability"),
                    "last_updated": "never",
                    "days_stale": "∞",
                    "action": "REVIEW — 从未更新",
                })
                continue

            try:
                updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                delta = (now - updated).days
                if delta >= stale_days:
                    # Check if there are recent events linked to this node
                    linked_recent = 0
                    if self.db_path.exists():
                        with sqlite3.connect(self.db_path) as conn:
                            linked_recent = conn.execute("""
                                SELECT COUNT(*) FROM event_node_links l
                                JOIN events e ON l.event_id = e.id
                                WHERE l.node_id = ? AND e.timestamp >= ?
                            """, (nid, cutoff)).fetchone()[0]

                    if linked_recent > 0:
                        stale.append({
                            "node_id": nid,
                            "label": node.get("label", nid),
                            "probability": node.get("probability"),
                            "last_updated": last_updated[:10],
                            "days_stale": delta,
                            "recent_events": linked_recent,
                            "action": f"STALE — {linked_recent} 条新事件但概率未更新",
                        })
            except (ValueError, TypeError):
                pass

        return sorted(stale, key=lambda x: x.get("recent_events", 0), reverse=True)

    # ── 3. Causal Chain Verification ───────────────────────

    def verify_chains(self) -> list[dict]:
        """Check key causal chains: did transmission happen in predicted order?
        
        Defines expected chains and checks which links have manifested.
        """
        # Key chains from v3.0 framework
        chains = [
            {
                "id": "blockade_to_politics",
                "label": "封锁→油价→汽油→政治反弹→战争决策",
                "nodes": ["hormuz_blockade", "oil_price_100", "gasoline_price_surge",
                          "us_domestic_pressure", "conflict_deescalation"],
                "expected_order": True,
                "description": "物理封锁→能源价格→终端消费→政治压力→决策变化",
            },
            {
                "id": "minesweep_bottleneck",
                "label": "扫雷瓶颈→保险→通行恢复",
                "nodes": ["minesweeping_bottleneck", "shipping_insurance_collapse",
                          "hormuz_blockade"],
                "expected_order": True,
                "description": "Q2串联约束: 扫雷能力→保险恢复→海峡重开",
            },
            {
                "id": "energy_to_stagflation",
                "label": "能源危机→通胀→滞胀→衰退",
                "nodes": ["energy_crisis", "input_inflation_transmission",
                          "global_stagflation", "equity_correction"],
                "expected_order": True,
                "description": "供给冲击→PPI/CPI传导→宏观滞胀→市场重定价",
            },
            {
                "id": "escalation_spiral",
                "label": "升级螺旋: IRGC攻击→美方升级→IRGC报复",
                "nodes": ["irgc_command_fragmentation", "conflict_protracted",
                          "regional_spillover"],
                "expected_order": False,  # feedback loop, no linear order
                "description": "正反馈回路: 碎片化指挥→持久化→外溢→更多碎片化",
            },
        ]

        nodes = self.dag.get("nodes", {})
        results = []

        for chain in chains:
            chain_status = {
                "id": chain["id"],
                "label": chain["label"],
                "description": chain["description"],
                "links": [],
                "manifested": 0,
                "total": len(chain["nodes"]),
                "broken_at": None,
            }

            prev_prob = None
            for i, nid in enumerate(chain["nodes"]):
                if nid not in nodes:
                    chain_status["links"].append({
                        "node": nid,
                        "status": "MISSING",
                        "probability": None,
                    })
                    if chain_status["broken_at"] is None:
                        chain_status["broken_at"] = nid
                    continue

                node = nodes[nid]
                prob = node.get("probability", 0)
                status = "HIGH" if prob > 0.7 else "MEDIUM" if prob > 0.3 else "LOW"

                if prob > 0.5:
                    chain_status["manifested"] += 1

                # Check if chain is "breaking" — earlier node high but later node low
                if chain["expected_order"] and prev_prob is not None:
                    if prev_prob > 0.8 and prob < 0.3:
                        if chain_status["broken_at"] is None:
                            chain_status["broken_at"] = nid

                chain_status["links"].append({
                    "node": nid,
                    "label": node.get("label", nid)[:40],
                    "status": status,
                    "probability": prob,
                })
                prev_prob = prob

            chain_status["health"] = (
                "✅ FLOWING" if chain_status["manifested"] == chain_status["total"]
                else "⚠️ PARTIAL" if chain_status["manifested"] > chain_status["total"] / 2
                else "❌ BLOCKED"
            )
            results.append(chain_status)

        return results

    # ── 4. Noise Reclassification Audit ────────────────────

    def audit_noise_classification(self) -> dict:
        """Audit: are we correctly separating signal from noise?
        
        Rule: classify by WORDS vs ACTIONS, not by person.
        Trump tweet = noise. Trump orders Kharg Island strike = action = signal.
        """
        signal_path = self.data_dir / "signal_status.json"
        if not signal_path.exists():
            return {"error": "no signal_status.json"}

        with open(signal_path) as f:
            signals = json.load(f)

        audit = {
            "rule": "words vs actions, not person-based",
            "issues": [],
            "recommendations": [],
        }

        # Check if any signals are classified by person rather than action type
        all_signals = []
        for category in ["deescalation", "escalation"]:
            data = signals.get(category, {})
            if isinstance(data, dict):
                for layer_name, layer_signals in data.items():
                    if isinstance(layer_signals, list):
                        all_signals.extend(layer_signals)
            elif isinstance(data, list):
                all_signals.extend(data)

        for sig in all_signals:
            notes = (sig.get("notes") or "") + " " + (sig.get("evidence") or "")
            sid = sig.get("id", "")

            # Flag signals that mention "noise" based on person
            if "noise" in notes.lower() and any(
                name in notes.lower() for name in ["trump", "irgc声明", "官方声明"]
            ):
                # Check if the signal distinguishes words from actions
                if "行动" not in notes and "action" not in notes.lower():
                    audit["issues"].append({
                        "signal_id": sid,
                        "problem": "噪声分类基于人物而非行为类型",
                        "current": notes[:100],
                        "fix": "区分: 该人物的言辞=噪声, 该人物的行动(调兵/打击/签署命令)=信号",
                    })

        # Check for recent high-impact actions that might be misclassified as noise
        if self.db_path.exists():
            cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()[:10]
            with sqlite3.connect(self.db_path) as conn:
                action_events = conn.execute("""
                    SELECT headline, significance FROM events
                    WHERE significance >= 5
                      AND timestamp >= ?
                      AND (headline LIKE '%strike%' OR headline LIKE '%attack%'
                           OR headline LIKE '%order%' OR headline LIKE '%deploy%'
                           OR headline LIKE '%launch%' OR headline LIKE '%bomb%')
                    ORDER BY significance DESC
                    LIMIT 10
                """, (cutoff,)).fetchall()

                for headline, sig in action_events:
                    audit["recommendations"].append({
                        "event": headline[:80],
                        "significance": sig,
                        "note": "高成本行动 — 确保不被噪声过滤器屏蔽",
                    })

        return audit

    # ── Full Report ────────────────────────────────────────

    def full_report(self) -> str:
        """Generate complete structural verification report."""
        lines = ["# 结构性验证报告", ""]
        now = datetime.now(timezone.utc)
        lines.append(f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")

        # 1. Omissions
        omissions = self.detect_omissions()
        lines.append(f"## 1. 盲区检测 ({len(omissions)} 个遗漏)")
        lines.append("")
        if omissions:
            for o in omissions[:10]:
                lines.append(f"- **{o['headline'][:60]}** (sig={o['significance']}) — {o['action']}")
        else:
            lines.append("✅ 无重大遗漏")
        lines.append("")

        # 2. Stale nodes
        stale = self.detect_stale_nodes()
        lines.append(f"## 2. 停滞节点 ({len(stale)} 个)")
        lines.append("")
        if stale:
            for s in stale[:10]:
                lines.append(f"- **{s['label'][:40]}** P={s['probability']} | "
                             f"最后更新: {s['last_updated']} | {s['action']}")
        else:
            lines.append("✅ 所有节点活跃")
        lines.append("")

        # 3. Causal chains
        chains = self.verify_chains()
        lines.append("## 3. 因果链验证")
        lines.append("")
        for c in chains:
            lines.append(f"### {c['label']} {c['health']}")
            lines.append(f"_{c['description']}_")
            lines.append("")
            for link in c["links"]:
                prob_str = f"{link['probability']:.0%}" if link['probability'] is not None else "N/A"
                label = link.get('label', link['node'])
                lines.append(f"  {'→' if link != c['links'][0] else '⊙'} {label} [{link['status']}] {prob_str}")
            if c["broken_at"]:
                lines.append(f"  ⚠️ 传导在 `{c['broken_at']}` 处断裂")
            lines.append("")

        # 4. Noise audit
        audit = self.audit_noise_classification()
        lines.append("## 4. 噪声分类审计")
        lines.append(f"_规则: {audit.get('rule', 'N/A')}_")
        lines.append("")
        issues = audit.get("issues", [])
        if issues:
            for i in issues:
                lines.append(f"- ⚠️ `{i['signal_id']}`: {i['problem']}")
                lines.append(f"  修复: {i['fix']}")
        else:
            lines.append("✅ 噪声分类无问题")
        lines.append("")
        recs = audit.get("recommendations", [])
        if recs:
            lines.append("### 高成本行动（确认未被屏蔽）")
            for r in recs:
                lines.append(f"- [{r['significance']}★] {r['event']}")
        lines.append("")

        return "\n".join(lines)


def run_verification(data_dir: str = "data") -> str:
    """Run full structural verification and return report."""
    v = StructuralVerifier(data_dir)
    return v.full_report()
