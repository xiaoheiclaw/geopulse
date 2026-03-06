"""Report generation for GeoPulse."""
from __future__ import annotations

from datetime import datetime, timezone

from .models import DAG


class Reporter:
    """Generates human-readable reports from DAG state."""

    def daily_report(
        self,
        dag: DAG,
        events_summary: list[str] | None = None,
        old_dag: DAG | None = None,
        analysis: str = "",
        model_insights: list[dict] | None = None,
    ) -> str:
        """Generate a daily summary report."""
        gri = dag.global_risk_index()
        orders = dag.compute_orders()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines = [
            f"⚡ GeoPulse 日报 — {dag.scenario_label}",
            "━" * 30,
            f"📅 {today} | 📊 全局风险: {gri:.0f}/100",
            "",
        ]

        if events_summary:
            lines.append(f"📰 关键事件（共{len(events_summary)}条）")
            lines.append("")
            for ev in events_summary:
                lines.append(f"▸ {ev}")
            lines.append("")

        if old_dag:
            changes = self.compute_changes(old_dag, dag)
            if changes:
                lines.append("🔮 概率变动（变化 ≥5%）")
                lines.append("")
                lines.append("| 节点 | 概率 | 变化 |")
                lines.append("|------|------|------|")
                for c in changes:
                    direction = "↑" if c["delta"] > 0 else "↓"
                    lines.append(
                        f"| {c['label']} | {c['new_prob']:.2f} "
                        f"| {direction}{abs(c['delta'])*100:.0f}% |"
                    )
                lines.append("")

        # --- 按阶数（纵向） ---
        order_labels = {0: "触发层", 1: "直接冲击", 2: "传导效应", 3: "深层连锁"}
        lines.append("🌐 因果网络（按传导阶数）")
        lines.append("")

        max_order = max(orders.values()) if orders else 0
        for order in range(max_order + 1):
            nodes_at_order = sorted(
                [nid for nid, o in orders.items() if o == order],
                key=lambda nid: -dag.nodes[nid].probability,
            )
            if not nodes_at_order:
                continue
            label = order_labels.get(order, f"{order}阶")
            lines.append(f"{order}阶 — {label}")
            for nid in nodes_at_order:
                node = dag.nodes[nid]
                domains_str = "/".join(node.domains)
                lines.append(
                    f"▸ {node.label} → {node.probability:.2f} [{domains_str}]"
                )
            lines.append("")

        # --- 按领域（横向） ---
        all_domains = ["军事", "能源", "经济", "科技", "金融", "政治", "社会"]
        domain_nodes: dict[str, list[str]] = {d: [] for d in all_domains}
        for nid, node in dag.nodes.items():
            for d in node.domains:
                if d in domain_nodes:
                    domain_nodes[d].append(nid)

        active_domains = {d: nids for d, nids in domain_nodes.items() if nids}
        if active_domains:
            lines.append("🏷️ 领域全景")
            lines.append("")
            for domain in all_domains:
                nids = domain_nodes.get(domain, [])
                if not nids:
                    continue
                sorted_nids = sorted(nids, key=lambda n: -dag.nodes[n].probability)
                lines.append(f"【{domain}】")
                for nid in sorted_nids:
                    node = dag.nodes[nid]
                    order = orders.get(nid, 0)
                    lines.append(
                        f"  {order}阶 {node.label} → {node.probability:.2f}"
                    )
                lines.append("")

        if model_insights:
            lines.append("🧠 思维模型洞察")
            lines.append("")
            for mi in model_insights:
                lines.append(f"▸ [{mi['model']}] {mi['insight']}")
            lines.append("")

        return "\n".join(lines)

    def compute_changes(
        self, old_dag: DAG, new_dag: DAG, threshold: float = 0.05
    ) -> list[dict]:
        """Compute probability changes between two DAG versions."""
        changes = []
        for nid, new_node in new_dag.nodes.items():
            old_node = old_dag.nodes.get(nid)
            if old_node is None:
                continue
            delta = new_node.probability - old_node.probability
            if abs(delta) >= threshold:
                changes.append({
                    "node_id": nid,
                    "label": new_node.label,
                    "old_prob": old_node.probability,
                    "new_prob": new_node.probability,
                    "delta": delta,
                })
        return sorted(changes, key=lambda x: abs(x["delta"]), reverse=True)

    def node_detail(self, dag: DAG, node_id: str) -> str:
        """Generate a detailed report for a single node."""
        node = dag.nodes.get(node_id)
        if not node:
            return f"节点 {node_id} 不存在"

        orders = dag.compute_orders()
        parents = dag.parent_nodes(node_id)
        children = dag.child_nodes(node_id)

        lines = [
            f"📍 {node.label}",
            f"概率: {node.probability:.2f} | 置信度: {node.confidence:.2f}"
            f" | 阶数: {orders.get(node_id, '?')} | 类型: {node.node_type}",
            f"领域: {', '.join(node.domains)}",
        ]

        if node.time_horizon:
            lines.append(f"时间窗口: {node.time_horizon}")

        # Temporal probability distribution
        if node.time_phases:
            lines.extend(["", "📊 概率时间分布:"])
            for phase in node.time_phases:
                bar_len = int(phase.prob_density * 50)
                bar = "█" * bar_len + "░" * max(0, 10 - bar_len)
                lines.append(f"  {phase.weeks:>6} {bar} {phase.prob_density:.0%} | {phase.label}")
                if phase.triggers:
                    lines.append(f"         触发: {'; '.join(phase.triggers[:2])}")
                if phase.signals:
                    lines.append(f"         信号: {'; '.join(phase.signals[:2])}")
                if phase.actions:
                    lines.append(f"         行动: {'; '.join(phase.actions[:1])}")

        # Dialectic reasoning
        if node.dialectic:
            d = node.dialectic
            lines.extend([
                "", "⚖️ 辩证推理:",
                f"  正论: {d.thesis}",
                f"  反论: {d.antithesis}",
                f"  合论: {d.synthesis}",
            ])
            if d.revision_history:
                lines.append("  修正历史:")
                for rev in d.revision_history:
                    lines.append(f"    · {rev}")

        lines.extend(["", "证据:"])
        for ev in node.evidence:
            lines.append(f"  ▸ {ev}")

        lines.extend(["", f"推理: {node.reasoning}", ""])

        if parents:
            lines.append("上游节点:")
            for pid in parents:
                p = dag.nodes[pid]
                edge = next(
                    e for e in dag.edges if e.source == pid and e.target == node_id
                )
                lines.append(
                    f"  ← {p.label}({p.probability:.2f}) [权重:{edge.weight:.2f}]"
                )

        if children:
            lines.append("下游节点:")
            for cid in children:
                c = dag.nodes[cid]
                edge = next(
                    e for e in dag.edges if e.source == node_id and e.target == cid
                )
                lines.append(
                    f"  → {c.label}({c.probability:.2f}) [权重:{edge.weight:.2f}]"
                )

        return "\n".join(lines)
