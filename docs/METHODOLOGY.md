# GeoPulse 方法论 v1.0

> 地缘政治风险的贝叶斯因果网络分析框架
> 
> 经过5轮红队审计，0致命伤/0硬伤通过投产

---

## 一、架构总览

```
新闻(24/7)
   ↓
P3 证据评级(API) → 评分 0-1.0
   ↓
P1 事件提取(API) → 方向 + 量级 + 似然比 (无具体数字)
   ↓
calibration.py → 贝叶斯 odds 乘法 → 概率更新
   ↓
red_team.py → 5项结构检查
P4 辩证质疑(API) → 定性偏离判断
   ↓
人工确认 → DAG 更新
   ↓
prediction_ledger → 快照预测
   ↓
continuous_resolve → 市场/新闻实时验证
   ↓
calibration_report → Brier score → auto_adjust
   ↓
人工确认 → 参数修正 → 下一轮
```

---

## 二、核心原则

### 1. LLM 不输出数字

LLM 只做定性判断，代码算定量。

| LLM 输出 | 代码计算 |
|---------|---------|
| 方向: up/down | magnitude → LR 基础值 |
| 量级: negligible/minor/moderate/significant/dramatic | likelihood_ratio → LR 缩放 |
| 似然比: 1-2 / 2-5 / 5-10 / >10 | transmission_order → 衰减 |
| 阶数: 1st/2nd/3rd/4th | confidence → LR 向 1 靠拢 |
| 置信度: 0-1 | direction → 取倒数 (if down) |

**为什么**: LLM 给具体数字有虚假精确感。"significant + LR 5-10 + 1st order" 比 "上调 11.2%" 更诚实。

### 2. 贝叶斯乘法更新

```
P_new = (P × LR) / (P × LR + 1-P)
```

- 同一节点多条证据按序更新，不线性叠加
- 永远在 [1%, 99%]（没有绝对确定）
- 越接近 0 或 1，变化越小（自然减速）

**为什么不用线性叠加**: 3 条 significant 新闻打 70% 的节点：
- 线性: 70% + 11.2% + 11.2% + 11.2% = **103.6%** ← 爆了
- 贝叶斯: 70% → 88% → 95.1% ← 自然收敛

### 3. DAG 价值在结构不在数字

66 个节点的具体概率有 ±15-20% 的不确定性。但因果链的**结构**是有价值的：

```
封锁 → 中断 → 缺口 → 危机 → 油价 → 通胀 → 滞胀 → Fed → 美债 → EM外流 → EM危机
```

知道传导路径 > 知道每个节点是 72% 还是 65%。

---

## 三、基础概率设定

### 方法选择树

```
节点已发生？── 是 → P=1.0
      │
      否
      │
有市场价格？── 是 → 供需模型 + 市场反推
      │
      否
      │
有历史类比？── 是 → 参考类 + 似然比调整
      │
      否 → 专家判断 + 宽区间
```

分解法不是独立方法，是结构工具。子概率仍需归入上述方法。

### 方法 A: 供需模型 + 市场反推

`conditional_prices.py`

从基本面算条件价格，不拍脑袋：
- 凸供给曲线: `premium = 5 × gap² + 7 × gap`
- 需求弹性按时间框架递增 (Week 1: -0.01 → Week 12: -0.12)
- 恐慌溢价半衰期 4 周
- 条件价格是**时间曲线**不是单点

从当前市价反推市场隐含概率：
```
P(封锁) = (Brent_actual - Brent_no_blockade) / (Brent_blockade - Brent_no_blockade)
```

**⚠ 限制**: 
- B-S 隐含概率是 Q-measure（风险中性），不是 P-measure（真实世界），尾部差 2-3 倍
- 市场价格包含风险溢价、流动性、投机持仓等非概率因素
- 定位: **参考点**，不是校准目标

### 方法 B: 参考类 + 似然比调整

```python
base_rate = 历史基础率  # 如: 4次对峙1次封锁 = 25%
调整因子 = [(原因, 似然比), ...]  # 如: ("空袭", 3.0)

# 含相关性修正
effective_lr = 1 + (lr - 1) × (1 - ρ)
```

**⚠ 限制**:
- 样本量通常 < 5，置信区间极宽
- 调整因子是主观的
- 相关因子不能当独立的乘（空袭 ×3.0 和领导人被杀 ×2.5 相关性 ρ=0.85）

### 方法 C: 专家判断

诚实承认不确定性。给宽区间，不假装精确。

### 多方法冲突仲裁

`aggregate_methods()`

- 区间重叠 → 取交集内的加权中点
- 区间不重叠 → FLAG + 优先级加权
- 优先级: 市场(1.0) > 供需模型(0.9) > 参考类(0.6) > 专家(0.4)

---

## 四、概率更新机制

### P1 事件提取

新闻 → LLM 提取结构化影响:

```json
{
  "node_id": "oil_price_100",
  "direction": "up",
  "magnitude": "significant",
  "likelihood_ratio": "5-10",
  "transmission_order": 1,
  "confidence": 0.8
}
```

### 校准映射表

`calibration.py`

| 量级 | Delta 范围 |
|------|-----------|
| negligible | 0-2% |
| minor | 2-5% |
| moderate | 5-10% |
| significant | 10-15% |
| dramatic | 15-30% |

| 阶数 | 衰减 |
|------|------|
| 1st | 100% |
| 2nd | 60% |
| 3rd | 35% |
| 4th | 20% |

### 红队偏离评估

P4/P2/P6 输出定性偏离 → `apply_deviation()`

| 偏离程度 | 似然比 |
|---------|--------|
| slight | 1.20 |
| moderate | 1.50 |
| strong | 2.00 |

---

## 五、时间模型

`time_adjusted_prob()`

概率不是静态的，有三种时间模式:

| 模式 | 适用 | 例子 |
|------|------|------|
| front_loaded | 如果会发生，早期更可能 | 封锁: Day0=87% → Day14=26% |
| cumulative | 随时间累积 | 需求崩塌: Day0=1% → Day90=40% |
| window | 特定时间窗口 | 选举前/会议前峰值 |

---

## 六、场景框架

### 独立维度（非互斥）

| 维度 | 选项 |
|------|------|
| 烈度 | 高 55% / 低 35% / 停火 10% |
| 地理 | 伊朗 40% / 多线 50% / 全球 10% |
| 时长 | <30d 25% / 1-3月 45% / >3月 30% |
| 升级 | 常规 55% / 核 20% / 大国 15% / 外交 10% |

### 交叉约束

**7 个不可能组合**: 低烈度+核门槛、停火+>3月 等
**4 个强相关对**: P(时长>3月 | 烈度=高) = 0.45 (vs 边际 0.30) 等

### 停火前置分支

停火(10%) 是前置条件。如果停火→四维度不适用。90% 未停火→再分配烈度/地理/时长/升级。

---

## 七、止损与确认（双向，贝叶斯推导）

每个关键节点有事前止损和确认触发器：

```
Brent破$100 (P=72%)
  ⬇ 止损: 3/21前没碰$100
     LR = P(没碰|不会破) / P(没碰|会破) = 0.90/0.15 = 6.0
     后验: 72% → 30%
  ⬆ 确认: 3/14前就破$100
     LR = P(早破|会破) / P(早破|不会破) = 0.50/0.05 = 10.0
     后验: 72% → 96%
```

**不等 deadline**: `continuous_resolve()` 每 4h 自动检查市场触发。

---

## 八、质量保障

### 结构检查 (代码)

`red_team.py` — 5 项自动检查:
1. 无环检测 (DAG 不能有循环)
2. 衰减检查 (传导链每跳必须衰减)
3. 跨域传导 (不能从军事直接跳到金融)
4. 节点定义 (每个非事件节点必须有量化阈值)
5. 时效检查 (证据不能超过 72h)

### 逻辑挑战 (LLM)

P4 辩证质疑 — 红队 LLM 强制找错:
- 高概率节点 (>60%): 构造 NOT 发生的最可信场景
- 高权重边 (>0.7): 找 A 发生但 B 没发生的案例
- 输出: overestimated/underestimated/fair + slight/moderate/strong

### 似然比相关性修正

```python
# 相关因子的 LR 向 1 衰减
effective_lr = 1 + (lr - 1) × (1 - ρ)

# ρ 默认值
same_action: 0.90      # 空袭→领导人被杀
same_causal_chain: 0.70
same_domain: 0.50      # 默认
cross_domain: 0.20
independent: 0.00
```

---

## 九、节点元数据

每个关键节点标注:

```yaml
node:
  probability: 0.72
  range: [0.30, 0.55]           # 区间，不是点估计
  method: supply_demand_model    # 来源方法
  derivation: "..."              # 推导过程
  
  falsification:                 # 止损（贝叶斯推导）
    criteria: "3/21前Brent未触及$100"
    deadline: "2026-03-21"
    lr: 6.0
    fail_target: 0.30
    
  confirmation:                  # 确认（双向）
    criteria: "3/14前Brent破$100"
    lr: 10.0
    confirm_target: 0.96
    
  decision_boundary:             # 区间有决策意义
    at_lower: "30%: 不对冲"
    at_upper: "55%: 持有call"
    threshold: 0.40
    
  reflexivity:                   # 反身性
    reflexive: true/false
    severity: low/medium/high
    
  adversarial:                   # 对抗性
    adversary: "伊朗IRGC海军"
    defense: "信号不绑定单一模式"
    range_widening: 0.10
```

---

## 十、校准闭环

```
DAG更新 → snapshot_dag() → 预测账本 (prediction_ledger.json)
                                     ↓
                     continuous_resolve() — 每4h市场+新闻自动检查
                                     ↓
                     resolve_prediction(outcome=1.0/0.0)
                                     ↓
                     calibration_report()
                     ├─ Brier score (0=完美, 0.25=随机)
                     ├─ 校准曲线 (5 区间)
                     ├─ 按方法分拆
                     └─ 偏差方向
                                     ↓
                     auto_adjust() — 需 ≥50 条已验证
                     ├─ 偏差>5% → 全局 shrinkage
                     ├─ 差方法 → 权重降 30% (下限 0.3)
                     └─ 区间 gap>10% → 标记修正
                                     ↓
                     人工确认 → 参数修正 → 下一轮
```

### 安全机制
- auto_apply = False，所有调整需人工确认
- 门槛 50 条（18 条做校准 = 噪声）
- Resolution criteria 创建时锁定，事后不可修改
- Resolver 应为非建模者（防自我验证偏差）

---

## 十一、4h Pipeline (Cron)

每 4 小时自动运行:

```
1. 新闻扫描 (web_search, 24/7)
   → Iran/Hormuz/IRGC/ceasefire/nuclear/oil
   → 重大事件 P0 推送

2. 信号监控 (交易日)
   → 12 个市场指标
   → baselines 更新

3. 连续校准
   → continuous_resolve (Brent到$100没？S&P到-5%没？)
   → track_progress (距离目标多远)

4. 推送
   → P0: 立即推送
   → P1: 汇总推送
   → P2: 只记 memory
```

---

## 十二、已知局限

| 局限 | 严重度 | 状态 |
|------|--------|------|
| 节点概率精度 ±15-20% | 结构性 | 不可消除，已承认 |
| 参考类样本 <5 | 中 | 已标注，给宽区间 |
| 条件价格依赖供给曲线参数 | 中 | 敏感性分析已做 |
| 校准需 ≥50 条数据 | 高→随时间缓解 | 首批 3/14 到 |
| 未建模的黑天鹅 | 结构性 | 不可消除 |
| 反身性（EM 资本外流） | 低 | 已标注 |
| 对抗性信号操纵 | 中 | 信号不绑定单一模式 |

### 理论上限

红队终审评估: **前 20% 分析师水平**。

> "框架的认识论骨架已经正确。剩余的不确定性已从方法论错误降级为参数校准，后者只能在实战中解决。"

---

## 十三、代码索引

| 文件 | 功能 | LOC |
|------|------|-----|
| `src/geopulse/calibration.py` | 贝叶斯更新 + 聚合 + 时间模型 + 相关性修正 | ~350 |
| `src/geopulse/calibration_tracker.py` | 预测账本 + Brier score + 闭环反馈 | ~300 |
| `src/geopulse/conditional_prices.py` | 供需模型条件价格 | ~120 |
| `src/geopulse/anchoring.py` | 参考点（非校准工具） | ~170 |
| `src/geopulse/red_team.py` | 5 项结构检查 | ~200 |
| `scripts/prompt_runner.py` | P1/P3/P4 API 自动化 | ~250 |
| `scripts/signal_monitor.py` | 12 个市场信号监控 | ~350 |
| `scripts/dag_diff.py` | DAG 版本对比 | ~100 |
| `scripts/gen_report.py` | 报告骨架生成 | ~100 |
| `prompts/prompt_library.md` | 6 个生产级 prompt 模板 | ~500 |

---

## 十四、红队审计历程

| 轮次 | 发现 | 修正 |
|------|------|------|
| R1 | 4 致命: 循环论证 / Q≠P / 条件价格拍脑袋 / 场景非 MECE | 止损 + anchoring 降级 + 独立维度 |
| R2 | 2 硬伤: 聚合规则 / 时间模型; 3 中度 | aggregate_methods + time_adjusted_prob + 方法层次 |
| R3 | 3 中度: 区间装饰 / 反身性 / 对抗性 | decision_boundary + reflexivity + adversarial |
| R4 | 1 残留: ρ 来源 | RHO_DEFAULTS + 投产批准 |
| R5 | 校准闭环: 样本不足 / resolution 偏差 | 门槛 50 / 降权下限 / criteria 锁定 / 连续 resolve |

---

*GeoPulse Methodology v1.0 — 2026-03-07*
*5 轮红队审计通过 · Ready for Production*
