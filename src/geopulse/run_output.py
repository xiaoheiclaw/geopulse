"""
GeoPulse v7.4 — RunOutput Schema (Pydantic v2)

一轮完整运行的结构化输出。所有下游消费（仓位调整、监控仪表盘、
SHS 更新、复盘审计）都从这个对象读取，不允许从中间层直接取值。

Reference: docs/v7.4/runtime_protocol.md
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Enums ────────────────────────────────────────────────────────────

class TriggerType(str, Enum):
    scheduled = "scheduled"
    event_driven = "event_driven"
    manual = "manual"


class Regime(str, Enum):
    A = "A"  # Structural — mechanical causal propagation
    B = "B"  # Strategic — game-theoretic resolution


class NodeType(str, Enum):
    M = "M"  # Mechanical
    S = "S"  # Strategic
    H = "H"  # Hybrid


class HorizonWindow(str, Enum):
    W1_5 = "W1_5"
    W6_16 = "W6_16"
    W17_25plus = "W17_25plus"


class Direction(str, Enum):
    long = "long"
    short = "short"
    hedge = "hedge"


class Urgency(str, Enum):
    watch = "watch"
    alert = "alert"
    act = "act"


class DivergenceResolution(str, Enum):
    new_branch = "new_branch"
    noted = "noted"
    escalated = "escalated"


class BackflowTarget(str, Enum):
    L2 = "L2"
    L4 = "L4"
    L5 = "L5"
    Regime = "Regime"


class ModelRole(str, Enum):
    P = "P"  # Productive — generates judgments
    D = "D"  # Disciplinary — challenges judgments


class ModelCost(str, Enum):
    light = "light"
    medium = "medium"
    heavy = "heavy"


class SHSAction(str, Enum):
    add = "add"
    update = "update"
    deprecate = "deprecate"


class ProposalType(str, Enum):
    add_node = "add_node"
    remove_node = "remove_node"
    add_edge = "add_edge"
    remove_edge = "remove_edge"
    retype_node = "retype_node"
    restructure_path = "restructure_path"


class ProposalUrgency(str, Enum):
    immediate = "immediate"
    next_run = "next_run"
    review = "review"


class ApprovalLevel(int, Enum):
    L1_AUTO = 1       # Low risk: leaf additions, new downstream edges
    L2_DEFERRED = 2   # Medium risk: retype, insert on main path, new S-node
    L3_HUMAN = 3      # High risk: delete, restructure, regime-affecting


# ── 0. GraphProposal (Phase 4: Graph Evolution) ─────────────────────

class ImpactAssessment(BaseModel):
    """GraphProposal 的影响评估"""
    affected_nodes: list[str] = Field(default_factory=list)
    affected_edges: list[str] = Field(default_factory=list)
    regime_impact: bool = Field(False, description="是否可能影响 Regime 判定")
    scenario_impact: list[str] = Field(default_factory=list)


class GraphProposal(BaseModel):
    """Phase 4: DAG 结构修改提案

    Agent 提案，代码验证，人类审批（可选）。
    概率回写是连续/可逆/局部的；结构修改是离散/难逆/全局的。
    """
    proposal_id: str
    type: ProposalType
    target: str = Field(..., description="目标节点或边 ID")
    payload: dict = Field(default_factory=dict, description="修改内容")
    justification: str = Field("", description="修改理由")
    source_evidence: list[str] = Field(default_factory=list)
    source_model: str = Field("", description="提出修改的模型 ID")
    impact_assessment: ImpactAssessment = Field(default_factory=ImpactAssessment)
    urgency: ProposalUrgency = Field(ProposalUrgency.next_run)
    auto_approvable: bool = Field(False, description="是否可自动批准")
    approval_level: ApprovalLevel = Field(ApprovalLevel.L2_DEFERRED)
    status: str = Field("pending", description="pending | approved | rejected | applied")


# ── 1. RunMeta ───────────────────────────────────────────────────────

class RunMeta(BaseModel):
    """本轮运行的元数据"""
    run_id: str = Field(..., description="本轮唯一标识")
    timestamp: datetime = Field(..., description="运行时间")
    trigger_type: TriggerType = Field(..., description="触发类型")
    trigger_event: Optional[str] = Field(None, description="触发本轮运行的事件描述")
    evidence_count: int = Field(0, ge=0, description="L1 处理的证据条数")
    run_duration_ms: int = Field(0, ge=0, description="总耗时 (ms)")


# ── 2. RegimeState ───────────────────────────────────────────────────

class FactorScores(BaseModel):
    """三因子评分 — 决定节点/全局属于 Regime A 还是 B"""
    SAD: float = Field(..., ge=0, le=1, description="Strategic Actor Density")
    PD: float = Field(..., ge=0, le=1, description="Payoff Dependence")
    NCC: float = Field(..., ge=0, le=1, description="Non-Cooperative Complexity")


class Hysteresis(BaseModel):
    """Regime 切换的滞后参数 — 防止高频震荡"""
    enter_threshold: float = Field(..., ge=0, le=1)
    exit_threshold: float = Field(..., ge=0, le=1)
    min_hold: str = Field(..., description="最低持续时间 (ISO 8601 duration)")
    time_in_current: str = Field(..., description="当前 Regime 已持续时间")


class RegimeState(BaseModel):
    """当前运行的体制状态"""
    current: Regime
    previous: Regime
    switched: bool = Field(False, description="本轮是否发生切换")
    held_since: datetime = Field(..., description="当前体制开始时间")
    factor_scores: FactorScores
    joint_score: float = Field(..., ge=0, le=1, description="三因子联合得分")
    hysteresis: Hysteresis


# ── 3. Scenario (L2a) ───────────────────────────────────────────────

class Scenario(BaseModel):
    """L2a 输出 — 状态分支定义"""
    id: str
    label: str = Field(..., description="分支名称, e.g. '有限冲突' / '快速谈判'")
    weight: float = Field(..., ge=0, le=1, description="本轮分支权重")
    weight_prev: float = Field(..., ge=0, le=1, description="上轮权重")
    premises: list[str] = Field(default_factory=list, description="成立前提")
    antithesis: str = Field("", description="最强反论")
    open_questions: list[str] = Field(default_factory=list, description="待求解问题")
    source_models: list[str] = Field(default_factory=list, description="生成/修正此分支的模型 ID")
    is_new: bool = Field(False, description="本轮新增分支")
    is_from_divergence: bool = Field(False, description="是否由模型分歧催生")

    @property
    def weight_delta(self) -> float:
        return self.weight - self.weight_prev


# ── 4. BottleneckNode (L2b) ──────────────────────────────────────────

class BottleneckNode(BaseModel):
    """L2b 输出 — 关键瓶颈节点"""
    node_id: str
    label: str
    type: NodeType
    parent_scenarios: list[str] = Field(default_factory=list, description="关联的 scenario IDs")
    path_importance: float = Field(..., ge=0, le=1, description="在主分支中的路径重要度")
    factor_scores: FactorScores = Field(..., description="节点级三因子")
    irreversible: bool = Field(False, description="不可逆标记")
    locked: bool = Field(False, description="本轮是否已被路径锁定")


# ── 5. EngineResult (L3 + L3.5) ─────────────────────────────────────

class MechResult(BaseModel):
    """L3 结构传播结果 — Regime A 主引擎"""
    node_id: str
    propagated_prob: float = Field(..., ge=0, le=1)
    upstream_drivers: list[str] = Field(default_factory=list)
    impact_magnitude: float = Field(0.0)


class Equilibrium(BaseModel):
    """候选均衡"""
    eq_id: str
    label: str
    probability: float = Field(..., ge=0, le=1)
    is_focal: bool = Field(False, description="是否为 Schelling focal point")


class StratResult(BaseModel):
    """L3.5 策略求解结果 — Regime B 主引擎"""
    node_id: str
    equilibria: list[Equilibrium] = Field(default_factory=list)
    selected_eq: str = Field("", description="选定的主均衡 ID")
    commitment_score: float = Field(0.0, ge=0, le=1, description="承诺可信度")
    exit_cost_ratio: float = Field(0.0, description="退出成本非对称比")


class HybridResult(BaseModel):
    """Hybrid 节点 — L3 基线 + L3.5 修正"""
    node_id: str
    baseline_prob: float = Field(..., ge=0, le=1, description="L3 基线")
    override_prob: float = Field(..., ge=0, le=1, description="L3.5 修正后")
    delta: float = Field(0.0, description="修正幅度")
    recomp_subgraph: list[str] = Field(default_factory=list, description="被重算的下游节点 IDs")
    iteration_converged: bool = Field(True, description="一轮回注后是否收敛")

    @model_validator(mode="after")
    def check_delta(self):
        expected = round(self.override_prob - self.baseline_prob, 6)
        if abs(self.delta - expected) > 0.01:
            self.delta = expected
        return self


class EngineResult(BaseModel):
    """L3 + L3.5 联合输出"""
    regime_used: Regime
    mechanical_nodes: list[MechResult] = Field(default_factory=list)
    strategic_nodes: list[StratResult] = Field(default_factory=list)
    hybrid_nodes: list[HybridResult] = Field(default_factory=list)


# ── 6. HorizonThesis (L4) ───────────────────────────────────────────

class HorizonThesis(BaseModel):
    """L4 输出 — 分窗口交易命题"""
    window: HorizonWindow
    thesis: str = Field(..., description="交易命题的自然语言表述")
    dominant_scenario: str = Field(..., description="支撑该命题的主分支 ID")
    confidence: float = Field(..., ge=0, le=1)
    tradeable_as: str = Field(..., description="资产表达方向, e.g. 'long vol', 'short duration'")
    key_assumption: str = Field(..., description="该命题最依赖的假设")
    kill_condition: str = Field(..., description="什么情况下该命题失效")


# ── 7. ExecutionPlan (L5) ────────────────────────────────────────────

class Position(BaseModel):
    """仓位建议"""
    asset: str
    direction: Direction
    sizing_note: str = Field("", description="定性/定量仓位建议")
    horizon: HorizonWindow
    linked_thesis: str = Field("", description="对应 HorizonThesis")
    entry_condition: str = Field("")
    stop_condition: str = Field("")


class Trigger(BaseModel):
    """监控触发器"""
    trigger_id: str
    signal: str = Field(..., description="监控信号描述")
    condition: str = Field(..., description="触发条件")
    action: str = Field(..., description="触发后执行什么")
    linked_node: Optional[str] = Field(None, description="关联的 bottleneck node")
    urgency: Urgency = Field(Urgency.watch)


class ExecutionPlan(BaseModel):
    """L5 输出 — 仓位 + 触发器"""
    positions: list[Position] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)


# ── 8. InvalidationSet ──────────────────────────────────────────────

class TradeInvalidation(BaseModel):
    position_ref: str
    condition: str
    action: str = Field(..., description="'adjust' | 'exit'")
    backflow_to: BackflowTarget


class ScenarioInvalidation(BaseModel):
    scenario_ref: str
    premise_broken: str
    evidence: str
    backflow_to: BackflowTarget = Field(BackflowTarget.L2)
    shs_writeback: bool = Field(False)


class RegimeInvalidation(BaseModel):
    current_regime: Regime
    contradiction: str
    backflow_to: BackflowTarget = Field(BackflowTarget.Regime)
    shs_writeback: bool = Field(False)


class InvalidationSet(BaseModel):
    """失效条件集 — 三级回流"""
    trade_level: list[TradeInvalidation] = Field(default_factory=list)
    scenario_level: list[ScenarioInvalidation] = Field(default_factory=list)
    regime_level: Optional[RegimeInvalidation] = None


# ── 9. ModelTrace ────────────────────────────────────────────────────

class ModelCall(BaseModel):
    """单次模型调用记录"""
    model_id: str
    layer: str = Field(..., description="在哪层被调用")
    role: ModelRole
    called_by: str = Field(..., description="Pipeline 哪个步骤发起")
    input_summary: str = Field("")
    output_summary: str = Field("")
    cost: ModelCost = Field(ModelCost.light)


class DivergenceFlag(BaseModel):
    """模型分歧标记 — 分歧不是故障，是信号"""
    flag_id: str
    layer: str
    model_a: str
    model_b: str
    topic: str
    model_a_says: str
    model_b_says: str
    resolution: DivergenceResolution = Field(DivergenceResolution.noted)
    spawned_scenario: Optional[str] = Field(None, description="如果催生了新分支")


class ModelTrace(BaseModel):
    """审计用 — 本轮所有模型调用记录"""
    models_loaded: list[ModelCall] = Field(default_factory=list)
    divergence_flags: list[DivergenceFlag] = Field(default_factory=list)
    total_model_calls: int = Field(0, ge=0)
    total_cost: ModelCost = Field(ModelCost.light)

    @model_validator(mode="after")
    def sync_call_count(self):
        if self.total_model_calls == 0 and self.models_loaded:
            self.total_model_calls = len(self.models_loaded)
        return self


# ── 10. SHSWriteback ────────────────────────────────────────────────

class SHSWriteback(BaseModel):
    """记忆更新 — 回写 Standing Hypothesis Set"""
    action: SHSAction
    hypothesis_ref: str = Field(..., description="SHS 中的假设名称")
    field_changed: str = Field(..., description="哪个字段被更新")
    old_value: str | None = Field("")
    new_value: str | None = Field("")
    trigger_reason: str = Field("", description="为什么更新")
    source_run_ids: list[str] = Field(default_factory=list, description="触发此更新的历史 run IDs")


# ── RunOutput (顶层) ────────────────────────────────────────────────

class RunOutput(BaseModel):
    """
    GeoPulse v7.4 一轮完整运行的结构化输出。

    所有下游消费都从这个对象读取：
    - execution_plan → 交易执行
    - invalidation → 监控系统
    - model_trace → 信用更新 (反馈回 Registry)
    - shs_writeback → 记忆更新 (反馈回 Memory)
    - divergence_flags → 下一轮 L2a 的候选分支
    """
    meta: RunMeta
    regime: RegimeState
    scenarios: list[Scenario] = Field(default_factory=list)
    bottlenecks: list[BottleneckNode] = Field(default_factory=list)
    engine_result: EngineResult
    horizon_theses: list[HorizonThesis] = Field(default_factory=list)
    execution_plan: ExecutionPlan = Field(default_factory=ExecutionPlan)
    invalidation: InvalidationSet = Field(default_factory=InvalidationSet)
    model_trace: ModelTrace = Field(default_factory=ModelTrace)
    shs_writeback: list[SHSWriteback] = Field(default_factory=list)
    graph_proposals: list[GraphProposal] = Field(default_factory=list, description="Phase 4: DAG 结构修改提案")

    # ── Dispatch 约束验证 ──

    @model_validator(mode="after")
    def check_pd_minimum(self):
        """约束 1: 每轮至少加载 1 个 D 类模型"""
        d_calls = [c for c in self.model_trace.models_loaded if c.role == ModelRole.D]
        if not d_calls and self.model_trace.models_loaded:
            raise ValueError(
                "Dispatch 约束违反: 每轮至少 1 个 D 类模型 (纪律不打折)"
            )
        return self

    @model_validator(mode="after")
    def check_high_confidence_audit(self):
        """约束 2: weight > 0.8 的分支必须被 D 类检验"""
        high_conf = [s for s in self.scenarios if s.weight > 0.8]
        if high_conf and self.model_trace.models_loaded:
            d_calls = [c for c in self.model_trace.models_loaded if c.role == ModelRole.D]
            if not d_calls:
                raise ValueError(
                    f"Dispatch 约束违反: {len(high_conf)} 个高置信度分支 "
                    f"(>{0.8}) 未被 D 类模型审计"
                )
        return self

    @model_validator(mode="after")
    def check_cost_budget(self):
        """成本预算验证 (D 类不计入)"""
        cost_map = {"light": 1, "medium": 3, "heavy": 7}
        budget = 40 if self.meta.trigger_type == TriggerType.manual else 20

        p_calls = [c for c in self.model_trace.models_loaded if c.role == ModelRole.P]
        total = sum(cost_map.get(c.cost.value, 1) for c in p_calls)

        if total > budget:
            raise ValueError(
                f"Dispatch 成本超限: P类消耗 {total} 单位 > 预算 {budget} 单位 "
                f"(trigger_type={self.meta.trigger_type.value})"
            )
        return self
