"""Red Team Pass: 对DAG更新进行自动化质量审计。

在每次DAG更新后运行，检查：
1. 事实/预测分类一致性
2. 概率校准（事实节点≥0.95，预测节点有区分度）
3. 重复节点检测
4. 孤立节点检测
5. 因果逻辑基本合理性
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .models import DAG


@dataclass
class AuditIssue:
    severity: str  # "error" | "warning" | "info"
    node_id: str
    category: str
    message: str


@dataclass
class AuditReport:
    issues: list[AuditIssue] = field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")
    
    def summary(self) -> str:
        lines = [f"🔍 红队审计: {self.error_count} errors, {self.warning_count} warnings, {len(self.issues)} total"]
        for issue in self.issues:
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[issue.severity]
            lines.append(f"  {icon} [{issue.category}] {issue.node_id}: {issue.message}")
        return "\n".join(lines)
    
    @property
    def passed(self) -> bool:
        return self.error_count == 0


def audit_dag(dag: DAG, old_dag: DAG | None = None) -> AuditReport:
    """对DAG执行全面红队审计。"""
    report = AuditReport()
    
    # 原有检查
    _check_fact_prediction_consistency(dag, report)
    _check_probability_calibration(dag, report)
    _check_duplicate_nodes(dag, report)
    _check_orphan_nodes(dag, report)
    _check_edge_validity(dag, report)
    _check_reasoning_quality(dag, report)
    _check_causal_depth(dag, report)
    
    # v25新增：结构性检查
    _check_cycles(dag, report)
    _check_low_decay_edges(dag, report)
    _check_cross_domain_edges(dag, report)
    _check_threshold_definitions(dag, report)
    
    if old_dag:
        _check_update_sanity(dag, old_dag, report)
    
    return report


def _check_fact_prediction_consistency(dag: DAG, report: AuditReport):
    """Check node_type vs probability consistency."""
    for nid, node in dag.nodes.items():
        # Event nodes that are confirmed should be >= 0.95
        if node.node_type == "event":
            reasoning = node.reasoning
            is_confirmed = any(reasoning.startswith(pat) for pat in ["已发生事实", "已发生。"])
            if is_confirmed and node.probability < 0.95:
                report.issues.append(AuditIssue(
                    severity="error",
                    node_id=nid,
                    category="fact_prob",
                    message=f"事件节点标注已发生但概率仅{node.probability:.2f}"
                ))
        
        # State/prediction nodes should have time_horizon
        if node.node_type in ("state", "prediction") and not node.time_horizon:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=nid,
                category="time_horizon",
                message=f"{node.node_type}节点缺少时间窗口(time_horizon)"
            ))
        
        if node.probability >= 1.0 and node.confidence < 0.8:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=nid,
                category="confidence",
                message=f"概率1.0但置信度仅{node.confidence:.2f}，矛盾"
            ))


def _check_probability_calibration(dag: DAG, report: AuditReport):
    """检查概率分布是否有区分度。"""
    probs = [n.probability for n in dag.nodes.values()]
    
    # Check clustering
    high_cluster = sum(1 for p in probs if p >= 0.9)
    total = len(probs)
    if total > 5 and high_cluster / total > 0.7:
        report.issues.append(AuditIssue(
            severity="warning",
            node_id="*",
            category="calibration",
            message=f"{high_cluster}/{total}个节点概率≥0.9，缺乏区分度"
        ))
    
    # Check prediction nodes specifically
    pred_probs = [n.probability for n in dag.nodes.values() if n.probability < 0.95]
    if len(pred_probs) >= 3:
        # Check if all clustered in narrow band
        if pred_probs:
            spread = max(pred_probs) - min(pred_probs)
            if spread < 0.15:
                report.issues.append(AuditIssue(
                    severity="warning",
                    node_id="*",
                    category="calibration",
                    message=f"预测节点概率极差仅{spread:.2f}，应有更大区分度"
                ))


def _check_duplicate_nodes(dag: DAG, report: AuditReport):
    """检测可能重复的节点（基于label相似度）。"""
    labels = [(nid, n.label) for nid, n in dag.nodes.items()]
    for i, (id1, label1) in enumerate(labels):
        for id2, label2 in labels[i+1:]:
            # Simple overlap check: >50% character overlap
            chars1 = set(label1)
            chars2 = set(label2)
            overlap = len(chars1 & chars2) / max(len(chars1), len(chars2), 1)
            if overlap > 0.7 and len(label1) > 5:
                report.issues.append(AuditIssue(
                    severity="warning",
                    node_id=f"{id1} vs {id2}",
                    category="duplicate",
                    message=f"可能重复: '{label1}' vs '{label2}'"
                ))


def _check_orphan_nodes(dag: DAG, report: AuditReport):
    """检测孤立节点（无入边也无出边）。"""
    connected = set()
    for edge in dag.edges:
        connected.add(edge.source)
        connected.add(edge.target)
    
    for nid in dag.nodes:
        if nid not in connected:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=nid,
                category="orphan",
                message="孤立节点：无入边也无出边"
            ))


def _check_edge_validity(dag: DAG, report: AuditReport):
    """检查边的基本合理性。"""
    for edge in dag.edges:
        if edge.source not in dag.nodes:
            report.issues.append(AuditIssue(
                severity="error",
                node_id=edge.source,
                category="edge_invalid",
                message=f"边的源节点不存在: {edge.source} -> {edge.target}"
            ))
        if edge.target not in dag.nodes:
            report.issues.append(AuditIssue(
                severity="error",
                node_id=edge.target,
                category="edge_invalid",
                message=f"边的目标节点不存在: {edge.source} -> {edge.target}"
            ))
        if edge.weight <= 0 or edge.weight > 1:
            report.issues.append(AuditIssue(
                severity="error",
                node_id=f"{edge.source}->{edge.target}",
                category="edge_weight",
                message=f"边权重{edge.weight}超出(0,1]范围"
            ))
        if not edge.reasoning or len(edge.reasoning) < 3:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=f"{edge.source}->{edge.target}",
                category="edge_reasoning",
                message="边缺少因果解释"
            ))


def _check_reasoning_quality(dag: DAG, report: AuditReport):
    """检查reasoning是否太短或太空泛。"""
    vague_phrases = ["可能", "也许", "大概", "不确定"]
    for nid, node in dag.nodes.items():
        if not node.reasoning or len(node.reasoning) < 10:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=nid,
                category="reasoning_short",
                message="Reasoning过短(<10字)，无法支撑概率判断"
            ))
        
        if not node.evidence:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=nid,
                category="evidence_missing",
                message="缺少证据来源"
            ))


def _check_update_sanity(dag: DAG, old_dag: DAG, report: AuditReport):
    """对比更新前后，检查是否有不合理的大幅变动。"""
    for nid, node in dag.nodes.items():
        if nid in old_dag.nodes:
            old_prob = old_dag.nodes[nid].probability
            new_prob = node.probability
            delta = abs(new_prob - old_prob)
            
            if delta > 0.3:
                report.issues.append(AuditIssue(
                    severity="warning",
                    node_id=nid,
                    category="big_swing",
                    message=f"概率大幅变动: {old_prob:.2f} -> {new_prob:.2f} (Δ{delta:.2f})，需要强证据支撑"
                ))


def _check_causal_depth(dag: DAG, report: AuditReport):
    """检测DAG因果链深度。标记最大深度<4的根节点。"""
    from collections import defaultdict
    
    # Build adjacency
    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, set[str]] = defaultdict(set)
    for edge in dag.edges:
        children[edge.source].append(edge.target)
        parents[edge.target].add(edge.source)
    
    # Find roots (event nodes with no parents, or nodes with no parents)
    roots = [nid for nid in dag.nodes if nid not in parents]
    
    # BFS max depth from each root
    def max_depth(start: str) -> int:
        visited = set()
        queue = [(start, 0)]
        best = 0
        while queue:
            nid, d = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            best = max(best, d)
            for kid in children.get(nid, []):
                if kid not in visited:
                    queue.append((kid, d + 1))
        return best
    
    for root in roots:
        depth = max_depth(root)
        if depth < 3 and len(children.get(root, [])) > 0:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=root,
                category="shallow_chain",
                message=f"因果链最大深度仅{depth}阶，建议推演至4阶以上"
            ))
    
    # Also check: leaf prediction nodes that could have downstream effects
    leaf_predictions = [
        nid for nid, n in dag.nodes.items()
        if n.node_type == "prediction" 
        and nid not in children
        and n.probability >= 0.3
    ]
    
    if len(leaf_predictions) > len(dag.nodes) * 0.4:
        report.issues.append(AuditIssue(
            severity="warning",
            node_id="*",
            category="shallow_chain",
            message=f"{len(leaf_predictions)}个预测节点是叶子节点(无下游)，可能存在未建模的传导链"
        ))


# ═══════════════════════════════════════════
# v25新增检查（此前每次临时手写，现在固化）
# ═══════════════════════════════════════════

def _check_cycles(dag: DAG, report: AuditReport):
    """检测有向图中的环。DAG不允许有环。"""
    from collections import defaultdict
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in dag.edges:
        adj[edge.source].append(edge.target)
    
    visited: set[str] = set()
    rec_stack: set[str] = set()
    
    def dfs(v: str, path: list[str]):
        visited.add(v)
        rec_stack.add(v)
        for u in adj.get(v, []):
            if u not in visited:
                dfs(u, path + [u])
            elif u in rec_stack:
                cycle = path[path.index(u):] + [u]
                report.issues.append(AuditIssue(
                    severity="error",
                    node_id=cycle[0],
                    category="cycle",
                    message=f"循环依赖: {' → '.join(cycle)}"
                ))
        rec_stack.discard(v)
    
    for v in dag.nodes:
        if v not in visited:
            dfs(v, [v])


def _check_low_decay_edges(dag: DAG, report: AuditReport):
    """检测衰减过低的边（父子概率差<4%）。
    
    传导链每跳应有合理衰减，否则等于同义重复。
    DT反馈(2026-03-07): "92%→92%→92%不是因果传导，是同一件事说了三遍。"
    """
    for edge in dag.edges:
        source = dag.nodes.get(edge.source)
        target = dag.nodes.get(edge.target)
        if not source or not target:
            continue
        if source.node_type == "event":
            continue  # Event→State的第一跳可以不衰减
        
        sp = source.probability
        tp = target.probability
        if abs(sp - tp) < 0.04 and sp > 0:
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=f"{edge.source}->{edge.target}",
                category="low_decay",
                message=f"衰减过低: {sp:.0%}→{tp:.0%} (Δ{abs(sp-tp):.0%})，考虑是否需要中间节点"
            ))


def _check_cross_domain_edges(dag: DAG, report: AuditReport):
    """检测跨域直连（无共享domain的边）。
    
    跨域边通常需要中间节点来解释传导机制。
    DT反馈(2026-03-07): "封锁→危机之间还要有别的因子。"
    """
    for edge in dag.edges:
        source = dag.nodes.get(edge.source)
        target = dag.nodes.get(edge.target)
        if not source or not target:
            continue
        if source.node_type == "event":
            continue
        
        sd = set(source.domains) if source.domains else set()
        td = set(target.domains) if target.domains else set()
        
        if sd and td and not sd.intersection(td):
            report.issues.append(AuditIssue(
                severity="warning",
                node_id=f"{edge.source}->{edge.target}",
                category="cross_domain",
                message=f"跨域直连: [{','.join(sd)}]→[{','.join(td)}]，考虑加桥接节点"
            ))


def _check_threshold_definitions(dag: DAG, report: AuditReport):
    """检查非Event节点是否有量化阈值定义。
    
    每个节点的reasoning应包含"定义:"开头的量化触发条件。
    DT反馈(2026-03-07): "霍尔木兹封锁和全球能源危机定义清楚。"
    """
    for nid, node in dag.nodes.items():
        if node.node_type == "event":
            continue
        reasoning = node.reasoning or ""
        if "定义:" not in reasoning:
            report.issues.append(AuditIssue(
                severity="error",
                node_id=nid,
                category="no_definition",
                message=f"缺少量化阈值定义（reasoning中无'定义:'字段）"
            ))
