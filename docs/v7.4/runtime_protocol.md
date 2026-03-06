# GeoPulse v7.4 — 运行时协议

## Part A: 运行时输出 Schema

一轮完整运行结束后，系统输出一个结构化对象 `RunOutput`。所有下游消费（仓位调整、监控仪表盘、SHS 更新、复盘审计）都从这个对象读取，不允许从中间层直接取值。

---

### RunOutput 顶层结构

```
RunOutput {
  meta              : RunMeta
  regime            : RegimeState
  scenarios         : Scenario[]
  bottlenecks       : BottleneckNode[]
  engine_result     : EngineResult
  horizon_theses    : HorizonThesis[]
  execution_plan    : ExecutionPlan
  invalidation      : InvalidationSet
  model_trace       : ModelTrace
  shs_writeback     : SHSWriteback[]
}
```

---

### 各字段定义

#### 1. RunMeta

```
RunMeta {
  run_id            : string          // 本轮唯一标识
  timestamp         : datetime        // 运行时间
  trigger_type      : enum            // scheduled | event_driven | manual
  trigger_event     : string | null   // 触发本轮运行的事件描述
  evidence_count    : int             // L1 处理的证据条数
  run_duration_ms   : int             // 总耗时
}
```

#### 2. RegimeState

```
RegimeState {
  current           : "A" | "B"
  previous          : "A" | "B"
  switched          : bool            // 本轮是否发生切换
  held_since        : datetime        // 当前体制开始时间
  factor_scores     : {
    SAD             : float [0,1]     // 加权聚合后
    PD              : float [0,1]
    NCC             : float [0,1]
  }
  joint_score       : float [0,1]     // 三因子联合得分
  hysteresis        : {
    enter_threshold : float
    exit_threshold  : float
    min_hold        : duration
    time_in_current : duration
  }
}
```

#### 3. Scenario (L2a 输出)

```
Scenario {
  id                : string
  label             : string          // "有限冲突" / "快速谈判" 等
  weight            : float [0,1]     // 本轮分支权重
  weight_prev       : float [0,1]     // 上轮权重 (用于计算 delta)
  premises          : string[]        // 成立前提
  antithesis        : string          // 最强反论
  open_questions    : string[]        // 待求解问题
  source_models     : string[]        // 生成/修正此分支的模型 ID
  is_new            : bool            // 本轮新增分支
  is_from_divergence: bool            // 是否由模型分歧催生
}
```

#### 4. BottleneckNode (L2b 输出)

```
BottleneckNode {
  node_id           : string
  label             : string          // "制裁升级" / "央行决策" 等
  type              : "M" | "S" | "H" // 节点分类
  parent_scenarios  : string[]        // 关联的 scenario IDs
  path_importance   : float [0,1]     // 在主分支中的路径重要度
  factor_scores     : {               // 节点级三因子 (输入 regime 聚合)
    SAD             : float [0,1]
    PD              : float [0,1]
    NCC             : float [0,1]
  }
  irreversible      : bool            // 不可逆标记
  locked            : bool            // 本轮是否已被路径锁定
}
```

#### 5. EngineResult (L3 + L3.5 联合输出)

```
EngineResult {
  regime_used       : "A" | "B"
  mechanical_nodes  : MechResult[]
  strategic_nodes   : StratResult[]
  hybrid_nodes      : HybridResult[]
}

MechResult {
  node_id           : string
  propagated_prob   : float [0,1]     // L3 传导后概率
  upstream_drivers  : string[]        // 上游驱动节点
  impact_magnitude  : float           // 冲击强度
}

StratResult {
  node_id           : string
  equilibria        : Equilibrium[]   // 候选均衡
  selected_eq       : string          // 选定的主均衡 ID
  commitment_score  : float [0,1]     // 承诺可信度 (如适用)
  exit_cost_ratio   : float           // 退出成本非对称比
}

Equilibrium {
  eq_id             : string
  label             : string
  probability       : float [0,1]
  is_focal          : bool            // 是否为 Schelling focal point
}

HybridResult {
  node_id           : string
  baseline_prob     : float [0,1]     // L3 基线
  override_prob     : float [0,1]     // L3.5 修正后
  delta             : float           // 修正幅度
  recomp_subgraph   : string[]        // 被重算的下游节点 IDs
  iteration_converged : bool          // 一轮回注后是否收敛
}
```

#### 6. HorizonThesis (L4 输出)

```
HorizonThesis {
  window            : enum            // W1_5 | W6_16 | W17_25plus
  thesis            : string          // 交易命题的自然语言表述
  dominant_scenario : string          // 支撑该命题的主分支 ID
  confidence        : float [0,1]
  tradeable_as      : string          // 资产表达方向 (e.g. "long vol", "short duration")
  key_assumption    : string          // 该命题最依赖的假设
  kill_condition    : string          // 什么情况下该命题失效
}
```

#### 7. ExecutionPlan (L5 输出)

```
ExecutionPlan {
  positions         : Position[]
  triggers          : Trigger[]
}

Position {
  asset             : string
  direction         : "long" | "short" | "hedge"
  sizing_note       : string          // 定性/定量仓位建议
  horizon           : enum            // 对应哪个时间窗口
  linked_thesis     : string          // 对应 HorizonThesis
  entry_condition   : string
  stop_condition    : string
}

Trigger {
  trigger_id        : string
  signal            : string          // 监控信号描述
  condition         : string          // 触发条件
  action            : string          // 触发后执行什么
  linked_node       : string | null   // 关联的 bottleneck node
  urgency           : "watch" | "alert" | "act"
}
```

#### 8. InvalidationSet

```
InvalidationSet {
  trade_level       : TradeInvalidation[]
  scenario_level    : ScenarioInvalidation[]
  regime_level      : RegimeInvalidation | null
}

TradeInvalidation {
  position_ref      : string          // 关联的 Position
  condition         : string          // 触发条件
  action            : string          // "adjust" | "exit"
  backflow_to       : "L4" | "L5"
}

ScenarioInvalidation {
  scenario_ref      : string          // 关联的 Scenario ID
  premise_broken    : string          // 被破坏的前提
  evidence          : string          // 破坏性证据
  backflow_to       : "L2"
  shs_writeback     : bool            // 是否触发 SHS 更新
}

RegimeInvalidation {
  current_regime    : "A" | "B"
  contradiction     : string          // 与当前体制矛盾的证据
  backflow_to       : "Regime"
  shs_writeback     : bool
}
```

#### 9. ModelTrace (审计用)

```
ModelTrace {
  models_loaded     : ModelCall[]
  divergence_flags  : DivergenceFlag[]
  total_model_calls : int
  total_cost        : "light" | "medium" | "heavy"   // 本轮总调用成本
}

ModelCall {
  model_id          : string
  layer             : string          // 在哪层被调用
  role              : "P" | "D"
  called_by         : string          // Pipeline 哪个步骤发起
  input_summary     : string
  output_summary    : string
  cost              : "light" | "medium" | "heavy"
}

DivergenceFlag {
  flag_id           : string
  layer             : string
  model_a           : string
  model_b           : string
  topic             : string          // 分歧点的简要描述
  model_a_says      : string
  model_b_says      : string
  resolution        : "new_branch" | "noted" | "escalated"
  spawned_scenario  : string | null   // 如果催生了新分支
}
```

#### 10. SHSWriteback

```
SHSWriteback {
  action            : "add" | "update" | "deprecate"
  hypothesis_ref    : string          // SHS 中的假设名称
  field_changed     : string          // 哪个字段被更新
  old_value         : string
  new_value         : string
  trigger_reason    : string          // 为什么更新 (e.g. "repeated scenario invalidation")
  source_run_ids    : string[]        // 触发此更新的历史 run IDs
}
```

---

## Part B: 调度规则 (Dispatch Protocol)

Pipeline 在每层处理节点时，按以下规则决定是否向 Registry 请求模型加载。

---

### B.1 母规则

> **Pipeline 是唯一的调用发起方。模型永远不自触发。**

每层在执行任务时，遇到需要解释/评估/质疑的节点，向 Registry 发起 `ModelRequest`：

```
ModelRequest {
  requesting_layer  : string          // 发起请求的层 ID
  node_context      : string          // 当前处理的节点/分支
  task_type         : enum            // explain | evaluate | challenge | resolve
  regime            : "A" | "B"       // 当前运行体制
}
```

Registry 收到请求后，返回满足 `callable_when` 且 `scope` 匹配的候选模型列表，由 Pipeline 按以下规则做最终加载决策。

---

### B.2 默认模型集 (Always-On)

每轮运行必定加载的模型，无需条件判定。这些模型的 cost 必须为 light。

| 层 | 默认模型 | role | 理由 |
|---|---|---|---|
| L1 | Bayesian Updating | P | Regime A 基础计算范式 |
| L2a | 辩证质疑 | D | 每条分支必须有反论 |
| L3 | N阶推演 | P | 传导链展开的基本工具 |

规则：默认模型集 ≤ 3 个。超过 3 个需要显式论证为什么某模型值得 always-on 待遇。

---

### B.3 条件加载规则

非默认模型按以下条件加载：

**规则 3a：节点类型触发**

```
if node.type == "S" or node.type == "H":
    load 适用于当前层的博弈论类模型
    (e.g. Schelling Commitment, Fearon Audience Cost)
```

**规则 3b：Regime 触发**

```
if regime == "B":
    升级所有博弈论类模型的调用优先级
    降级纯传导类模型为可选

if regime == "A":
    传导类模型为主
    博弈类模型仅在 S/H 节点上加载
```

**规则 3c：置信度触发 (D 类强制加载)**

```
if any scenario.weight > 0.75:
    Pipeline 在 L2a 强制请求 Pre-Mortem
    // 高置信度是最需要质疑的时候
```

**规则 3d：分支类型触发**

```
if scenario 涉及技术范式转换:
    在 L2a 加载 Carlota Perez

if scenario 涉及供应链/产能瓶颈:
    在 L2b/L3 加载 Theory of Constraints
```

---

### B.4 高成本模型门槛

cost = heavy 的模型有额外加载条件：

```
heavy 模型加载条件 = callable_when 满足 AND 以下至少一条:
  (a) 该节点的 path_importance > 0.6
  (b) 当前 regime == "B" 且模型属于博弈论类
  (c) Pipeline 显式标记为 "deep_dive" 模式
```

原理：heavy 模型（如 Fearon Audience Cost）需要大量上下文构建。对边缘节点调用是浪费。只有在关键路径上才值得投入。

---

### B.5 P/D 最小组合

每轮运行必须满足的结构性约束：

```
约束 1: 每轮至少加载 1 个 D 类模型
         (系统不允许无质疑运行)

约束 2: 任何产出 scenario.weight > 0.8 的分支，
         必须被至少 1 个 D 类模型检验过

约束 3: D 类模型不受成本预算限制
         (纪律不打折)
```

原理：P 类模型会自然地被大量调用，因为它们直接产出 Pipeline 需要的填充值。D 类模型的价值是非线性的——大部分时候"没用"，关键时刻救命。最小组合约束防止系统在效率优化中丢掉纪律。

---

### B.6 冲突处理与上报

当同一层、同一节点上多个模型给出不同结论时：

```
Step 1: 标记 DivergenceFlag
        记录 model_a_says / model_b_says

Step 2: 评估分歧性质
        if 分歧在数值范围内 (e.g. 概率差 < 0.15):
            resolution = "noted"
            // 记录但不行动

        if 分歧在方向上矛盾 (e.g. 一个说升级一个说降温):
            resolution = "new_branch"
            // 上报 L2a，催生新分支
            spawned_scenario = 新分支 ID

        if 分歧涉及 regime 判断 (e.g. 一个说结构主导一个说策略主导):
            resolution = "escalated"
            // 上报 regime 重评估
```

原理：分歧不是故障，是信号。数值级分歧可以容忍；方向级分歧应该丰富分支空间；体制级分歧必须触发 regime 复审。

---

### B.7 模型信用更新规则

每轮运行结束后，根据 ModelTrace 更新 Registry 中的信用评分：

**P 类模型:**

```
每轮结束后回看:
  该模型的输出与后续 evidence 是否一致

信用更新:
  correct_direction  →  credit += α
  wrong_direction    →  credit -= β
  no_data_yet        →  不更新 (避免对慢变量惩罚)

降级条件:
  连续 3 轮 wrong_direction → 降为 optional
  (但不删除, 保留在 Registry 中)
```

**D 类模型:**

```
每轮结束后回看:
  该模型标记的风险, 后续是否出现相关 evidence

信用更新:
  flagged_risk_materialized   →  credit += γ (大幅加分)
  flagged_risk_not_happened   →  不扣分
  missed_risk_that_happened   →  credit -= δ

永不降级:
  D 类模型即使 credit 低也不降为 optional
  (纪律模型的价值在尾部, 不能用频率评判)
```

---

### B.8 单轮成本预算

每轮运行有一个总调用成本上限，防止系统过重：

```
cost_budget = {
  light  : 计 1 单位
  medium : 计 3 单位
  heavy  : 计 7 单位
}

default_budget    = 20 单位/轮
deep_dive_budget  = 40 单位/轮  (Pipeline 显式标记时)

D 类模型不计入预算 (约束 3: 纪律不打折)
```

原理：防止每轮都变成全模型齐上的"重型运算"。大部分轮次应该是轻量的——只有在关键事件/regime 切换/deep dive 时才开放更多预算。

---

## 附: RunOutput 与 Dispatch 的关系

```
Dispatch (Part B) 的每一条规则
        ↓
决定本轮加载哪些模型
        ↓
模型在 Pipeline 各层被调用
        ↓
填充 RunOutput (Part A) 的各个字段
        ↓
RunOutput 被下游消费:
  - execution_plan     → 交易执行
  - invalidation       → 监控系统
  - model_trace        → 信用更新 (反馈回 Registry)
  - shs_writeback      → 记忆更新 (反馈回 Memory)
  - divergence_flags   → 下一轮 L2a 的候选分支
```

也就是说：A 定义"系统交付什么"，B 定义"系统如何工作"。A 是合同，B 是施工规范。两者合在一起，就是 GeoPulse v7.4 从架构图到可执行协议的完整跨越。
