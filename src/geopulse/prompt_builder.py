"""Agent prompt construction — builds structured prompts for the v7.4 pipeline.

The prompt has three parts:
1. System: v7.4 protocol rules + Registry constitution + output schema
2. User: current run context (evidence, DAG, SHS, regime, dispatch plan)
3. Schema instruction: RunOutput JSON format specification
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from .dispatch import DispatchPlan
from .evidence import Evidence
from .registry import ModelCard
from .run_output import (
    RegimeState,
    RunOutput,
    TriggerType,
)
from .shs import Hypothesis


class AgentContext(BaseModel):
    """Complete context package for the Agent."""

    trigger_type: TriggerType
    trigger_event: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    dag_summary: dict = Field(default_factory=dict)
    dag_baseline: dict = Field(default_factory=dict)  # L3 Noisy-OR pre-computed probs
    shs: list[Hypothesis] = Field(default_factory=list)
    regime: RegimeState
    dispatch_plan: DispatchPlan
    model_cards: list[ModelCard] = Field(default_factory=list)
    mental_models_text: str = ""
    previous_run_summary: str | None = None


class PromptBuilder:
    """Constructs system + user prompts for the Agent."""

    def build_system_prompt(self) -> str:
        """System prompt: v7.4 pipeline spec + Registry constitution + output schema."""
        return _SYSTEM_PROMPT + "\n\n" + self.build_run_output_schema_instruction()

    def build_user_prompt(self, context: AgentContext) -> str:
        """User prompt: current run context + instructions."""
        parts: list[str] = []

        # Trigger
        parts.append(f"## 触发: {context.trigger_type.value}")
        if context.trigger_event:
            parts.append(f"事件: {context.trigger_event}")

        # Evidence
        parts.append(f"\n## 新证据 ({len(context.evidence)} 条)")
        if context.evidence:
            ev_data = [e.model_dump(mode="json", exclude={"credibility", "affected_nodes", "impact_direction"}) for e in context.evidence]
            parts.append(json.dumps(ev_data, ensure_ascii=False, indent=2))
        else:
            parts.append("无新证据。")

        # SHS
        parts.append(f"\n## 当前 Standing Hypothesis Set ({len(context.shs)} 条)")
        if context.shs:
            shs_data = [
                {
                    "id": h.id,
                    "label": h.label,
                    "statement": h.statement,
                    "confidence": h.confidence,
                    "horizon": h.horizon,
                    "status": h.status,
                }
                for h in context.shs
                if h.status == "active"
            ]
            parts.append(json.dumps(shs_data, ensure_ascii=False, indent=2))
        else:
            parts.append("SHS 为空。")

        # DAG summary
        parts.append("\n## DAG 状态摘要")
        parts.append(json.dumps(context.dag_summary, ensure_ascii=False, indent=2))

        # L3 baseline
        parts.append("\n## L3 基线概率 (Noisy-OR 预计算)")
        if context.dag_baseline:
            # Only show top-20 by probability
            sorted_probs = sorted(
                context.dag_baseline.items(), key=lambda x: x[1], reverse=True
            )[:20]
            parts.append(json.dumps(dict(sorted_probs), ensure_ascii=False, indent=2))
        else:
            parts.append("无基线数据。")

        # Regime
        parts.append(f"\n## 当前 Regime: {context.regime.current.value}")
        parts.append(f"联合得分: {context.regime.joint_score}")
        parts.append(
            f"SAD={context.regime.factor_scores.SAD} "
            f"PD={context.regime.factor_scores.PD} "
            f"NCC={context.regime.factor_scores.NCC}"
        )

        # Dispatch plan
        parts.append(f"\n## 本轮可用模型 (预算: {context.dispatch_plan.budget_used}/{context.dispatch_plan.budget_limit})")
        if context.model_cards:
            for mc in context.model_cards:
                parts.append(
                    f"- **{mc.name}** ({mc.id}) — {mc.role.value}类/{mc.cost.value} — {mc.callable_when}"
                )
        else:
            parts.append("仅默认模型集。")

        # Mental models
        if context.mental_models_text:
            parts.append("\n## 思维模型库")
            parts.append(context.mental_models_text)

        # Previous run
        if context.previous_run_summary:
            parts.append("\n## 上轮 RunOutput 摘要")
            parts.append(context.previous_run_summary)

        # Instruction
        parts.append(_USER_INSTRUCTION)

        return "\n".join(parts)

    def build_run_output_schema_instruction(self) -> str:
        """Generate schema instruction for the Agent."""
        schema = RunOutput.model_json_schema()
        return (
            "## RunOutput JSON Schema\n\n"
            "你必须严格按照以下 schema 输出 JSON。不要输出任何非 JSON 内容。\n\n"
            "```json\n"
            + json.dumps(schema, ensure_ascii=False, indent=2)
            + "\n```"
        )


# ── Prompt templates ──

_SYSTEM_PROMPT = """\
你是 GeoPulse v7.4 Pipeline 的推理引擎（代号：战忽局）。

## 角色
你的职责是接收结构化 context（证据、DAG、SHS、Regime 状态），执行 L1→L2a→L2b→L3.5→L4→L5 分析流程，输出完整的 RunOutput JSON。

## Registry 宪法
1. 模型不生成判断，模型只生成视角
2. 判断由 Pipeline 生成（你就是 Pipeline 的推理部分）
3. Pipeline 是唯一的调用发起方，模型永远不自触发

## 分析流程
- **L1 证据评估**: 对每条证据评估可信度(credibility)，识别受冲击的 DAG 节点(affected_nodes)，判断冲击方向(impact_direction)
- **L2a 状态分支**: 维护/更新 scenario 分支（权重、前提、反论），使用辩证质疑模型
- **L2b 瓶颈识别**: 识别关键瓶颈节点，标注类型(M/S/H)和路径重要度
- **L3.5 策略求解**: 对 S/H 类节点进行博弈论分析（均衡、承诺可信度、退出成本），对 Hybrid 节点给出概率修正
- **L4 交易命题**: 按时间窗口(W1_5/W6_16/W17_25plus)输出交易命题
- **L5 执行计划**: 仓位建议 + 监控触发器

## 关键规则
- D 类模型（辩证质疑、Pre-Mortem、Taleb 反脆弱）的输出必须如实反映在 antithesis 和 invalidation 中
- weight > 0.8 的分支必须被 D 类模型审计
- 模型调用必须记录在 model_trace 中
- SHS 更新必须通过 shs_writeback 字段

## 输出格式
严格输出**紧凑** RunOutput JSON（单行，无缩进，无多余空格），不要输出任何额外文本。不要用 markdown 代码块包裹。"""

_USER_INSTRUCTION = """

---

请执行 L1→L2a→L2b→L3.5→L4→L5 分析流程，输出完整 RunOutput JSON。

注意：
1. run_id 格式: "run_{timestamp}" (例如 "run_20260306T120000Z")
2. 所有模型调用必须记录在 model_trace.models_loaded 中
3. 至少使用 1 个 D 类模型
4. evidence_count = 本轮处理的证据条数
5. 对每条证据填充 credibility, affected_nodes, impact_direction
6. 输出纯 JSON，不要包含 markdown 代码块标记"""
