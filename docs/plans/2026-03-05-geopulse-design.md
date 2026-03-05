# GeoPulse — 地缘政治概率传导追踪系统

> 设计文档 v1.0 | 2026-03-05

## 1. 项目概述

### 1.1 什么是 GeoPulse

GeoPulse 是一个自动化的地缘政治风险概率追踪系统。它持续监控新闻事件，维护一个贝叶斯因果网络（DAG），通过思维模型框架进行概率推理，追踪风险沿因果链条的逐级传导。

### 1.2 核心理念

地缘事件的影响像涟漪一样扩散：一个军事冲突可以传导到能源价格、再到电力成本、再到数据中心、再到 AI 产业——跨越完全不同的领域。GeoPulse 用 DAG 来建模这种**多阶、跨领域的因果传导**，并为每个节点维护实时概率。

### 1.3 MVP 范围

**美伊冲突**单一场景。覆盖从军事冲突到能源、经济、科技、金融市场的完整传导链条。

### 1.4 使用场景

1. **宏观态势感知**：结构化理解地缘风险的传导路径和概率
2. **投资决策辅助**：追踪风险传导到资产价格的概率，辅助仓位调整（后续可对接 Second Brain signal_engine）

### 1.5 运行方式

- 作为 OpenClaw agent 运行，复用现有 Telegram 通道
- **定时推送**：每日定时推送态势报告
- **按需查询**：可以对话询问具体节点/链条/领域的详情

---

## 2. 架构设计

### 2.1 系统总览

```
┌──────────────────────────────────────────────────────────┐
│                     GeoPulse Agent                        │
│                   (OpenClaw Runtime)                       │
│                                                           │
│  ┌───────────┐   ┌────────────┐   ┌───────────────────┐  │
│  │  Ingester  │──▶│  Analyzer   │──▶│    DAG Engine      │  │
│  │ (Readwise) │   │ (LLM 事件  │   │ (LLM + 思维模型   │  │
│  │            │   │  提取)      │   │  更新概率/结构)    │  │
│  └───────────┘   └────────────┘   └────────┬──────────┘  │
│                                             │             │
│                  ┌─────────────┐   ┌────────▼──────────┐  │
│                  │   Reporter   │◀──│   Propagator      │  │
│                  │ (格式化输出) │   │ (概率传导计算)     │  │
│                  └──────┬──────┘   └───────────────────┘  │
│                         │                                  │
│                         ▼                                  │
│                    Telegram 推送                           │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Mental Models Library (.md)              │  │
│  │  counterfactual / deterrence / brinkmanship / ...    │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

| 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Ingester** | 从 Readwise API 拉取新文章 | Readwise API | 原始文章列表 |
| **Analyzer** | LLM 从文章中提取结构化事件 | 原始文章 | 事件列表（JSON） |
| **DAG Engine** | LLM 决定是否新增/修改节点和边，更新概率 | 事件 + 当前 DAG + 思维模型 | 更新后的 DAG |
| **Propagator** | 根据 DAG 拓扑计算概率传导 | DAG | 传导后的概率 |
| **Reporter** | 生成结构化文本报告 | DAG + 变化记录 | Telegram 消息 |
| **Mental Models Library** | 提供思维模型框架注入 LLM prompt | .md 文件 | prompt 片段 |

### 2.3 数据流

```
1. Ingester 定时拉取 Readwise 新文章
2. Analyzer 逐篇用 LLM 提取事件：
   - 事件描述、相关实体、影响领域、时间、来源
   - 过滤噪音（纯情绪/标题党）
3. DAG Engine 接收事件批次：
   a. LLM 读取当前 DAG 状态 + 新事件 + 全部思维模型
   b. LLM 输出结构化决策：
      - 新增节点？（描述 + 领域 + 连接的边）
      - 调整概率？（哪些节点、新概率、理由）
      - 新增边？（因果关系 + 权重 + 推理）
      - 删除/合并节点？
   c. 系统验证 LLM 输出的合法性（无环、概率范围等）
   d. 应用变更到 DAG
4. Propagator 重新计算所有节点的传导概率
5. Reporter 比较更新前后的 DAG，生成变化报告
6. 推送到 Telegram
```

---

## 3. 数据模型

### 3.1 DAG 节点（Node）

```json
{
  "id": "eu_electricity_surge",
  "label": "欧洲电力涨价",
  "domains": ["能源", "经济"],
  "probability": 0.40,
  "confidence": 0.6,
  "evidence": [
    "2026-03-04: 欧洲天然气期货跳涨12%",
    "2026-03-05: 德国工业电价创新高"
  ],
  "reasoning": "霍尔木兹封锁导致LNG供应紧张，欧洲高度依赖中东气源",
  "last_updated": "2026-03-05T14:00:00+08:00",
  "created": "2026-03-03T10:00:00+08:00"
}
```

字段说明：
- `id`: 唯一标识，snake_case，由 LLM 生成
- `label`: 人类可读的中文标签
- `domains`: 所属领域列表。预定义领域：`军事`、`能源`、`经济`、`科技`、`金融`、`政治`、`社会`
- `probability`: 0.0-1.0，该事件发生的概率
- `confidence`: 0.0-1.0，LLM 对自己评估的信心度
- `evidence`: 支撑当前概率的证据列表（带日期）
- `reasoning`: LLM 的推理说明
- `last_updated`: 最后更新时间
- `created`: 创建时间

### 3.2 DAG 边（Edge）

```json
{
  "from": "strait_of_hormuz_closure",
  "to": "eu_electricity_surge",
  "weight": 0.7,
  "reasoning": "欧洲约15%天然气来自中东LNG，海峡封锁直接切断供应"
}
```

字段说明：
- `from` / `to`: 节点 ID
- `weight`: 0.0-1.0，条件概率系数。含义：当 from 发生时，它对 to 发生概率的贡献强度
- `reasoning`: 因果关系的解释

### 3.3 DAG 完整结构

```json
{
  "meta": {
    "scenario": "us_iran_conflict",
    "scenario_label": "美伊冲突",
    "version": 12,
    "updated": "2026-03-05T14:00:00+08:00",
    "global_risk_index": 42
  },
  "nodes": { "<id>": { ... }, ... },
  "edges": [ { ... }, ... ]
}
```

- `version`: 每次更新递增，用于追踪历史
- `global_risk_index`: 0-100，所有节点概率的加权综合指数

### 3.4 阶数（Order）

阶数**不存储在节点上**，而是由系统根据 DAG 拓扑**动态计算**：

```
order(node) = 到任意根节点（入度为0的节点）的最短路径长度
```

根节点（零阶）= 触发事件（如"美伊军事冲突"）
一阶 = 根节点的直接后果
二阶 = 一阶后果的后果
...以此类推

### 3.5 领域（Domain）

预定义领域枚举（MVP）：

| 领域 | 说明 | 示例节点 |
|------|------|---------|
| 军事 | 武装冲突、军事部署、代理人战争 | 美伊军事冲突、伊朗反击 |
| 能源 | 石油、天然气、电力、新能源 | 油价飙升、LNG争夺 |
| 经济 | 贸易、通胀、供应链、制造业 | 通胀加剧、供应链中断 |
| 科技 | 数据中心、AI、半导体、互联网 | 数据中心成本、AI产业冲击 |
| 金融 | 股票、期货、汇率、债券、加密 | WTI期货、避险情绪 |
| 政治 | 外交、制裁、联盟、选举 | 制裁升级、NATO分裂 |
| 社会 | 难民、民生、舆论 | 能源贫困、社会动荡 |

一个节点可以属于多个领域。

---

## 4. 概率传导算法

### 4.1 Noisy-OR 模型

使用 Noisy-OR 门计算多个父节点对子节点的联合影响：

```
P(B) = 1 - ∏(1 - P(Ai) × W(Ai→B))   对所有父节点 Ai
```

其中：
- `P(Ai)` = 父节点 i 的概率
- `W(Ai→B)` = 边 Ai→B 的权重（条件概率系数）

直觉：每个父节点独立地"尝试"触发子节点，只要有一个成功就触发。

### 4.2 传导计算流程

```
1. 找到所有根节点（入度为0）
2. 按拓扑排序遍历 DAG
3. 根节点的概率 = LLM 直接评估的概率（不传导）
4. 非根节点的概率 = max(LLM评估概率, Noisy-OR传导概率)
   - 取 max 是因为 LLM 可能基于直接证据给出更高的概率
5. 计算全局风险指数 = 加权平均（按节点重要性加权）
```

### 4.3 为什么不用完整贝叶斯推断

- 完整贝叶斯网络推断（如变量消元、信念传播）需要精确的条件概率表，LLM 无法提供这种精度
- Noisy-OR 是贝叶斯网络的常用简化，假设父节点独立作用，足够捕捉多因素叠加效应
- MVP 阶段不需要更复杂的模型

---

## 5. Mental Models Library（思维模型库）

### 5.1 设计原理

思维模型是**LLM 推理时的分析框架**。每个模型教 LLM 从特定角度分析地缘事件，提高概率评估的质量和一致性。

MVP 阶段模型数量有限（5-10 个），每次 DAG 更新时**全部注入** LLM prompt。后续模型库增长后可改为按事件类型选择性注入。

### 5.2 模型文件格式

每个模型是 `models/` 目录下的一个 `.md` 文件，固定格式：

```markdown
# 模型名称 (English Name)

## 来源
理论出处/作者

## 核心问题
这个模型回答什么问题？（1-2 句）

## 分析框架
1. 要素一
2. 要素二
3. ...

## Prompt 注入模板
当分析涉及 [场景] 时，考虑：
- 问题一？
- 问题二？
- ...
```

### 5.3 MVP 思维模型清单

| 模型 | 核心用途 |
|------|---------|
| **反事实推理** (Counterfactual) | 如果 X 没发生，概率会怎样？隔离因果效应 |
| **威慑理论** (Deterrence Theory, Schelling) | 威胁是否可信？承诺问题、观众成本 |
| **边缘策略** (Brinkmanship, Schelling) | 升级到什么程度会停？双方的红线在哪？ |
| **焦点理论** (Focal Points, Schelling) | 双方在哪个点自然协调/停战？ |
| **二阶效应** (Second-Order Effects) | 别人会怎么反应？反应的反应？ |
| **雾中决策** (Fog of War) | 信息不完整时的决策偏差，情报的可靠性 |
| **沉没成本与承诺升级** (Sunk Cost Escalation) | 已投入的成本如何影响继续升级的决策 |
| **不对称冲突** (Asymmetric Conflict) | 弱方如何利用非对称手段改变博弈结构 |

### 5.4 注入方式

在 DAG Engine 的 LLM prompt 中，思维模型以如下方式注入：

```
你是一个地缘政治分析师。以下是你的分析工具箱（思维模型），
在评估概率和因果关系时请灵活运用这些框架：

---
{所有思维模型的 "Prompt 注入模板" 部分拼接}
---

当前 DAG 状态：
{dag.json}

新事件：
{events}

请输出你的分析和 DAG 更新决策...
```

---

## 6. LLM Prompt 设计

### 6.1 Analyzer Prompt（事件提取）

```
你是一个新闻事件提取器。从以下文章中提取与"美伊冲突"相关的结构化事件。

如果文章与美伊冲突无关，返回空列表。
如果是纯情绪/标题党/没有实质信息，返回空列表。

每个事件输出为 JSON：
{
  "headline": "事件一句话描述（≤30字）",
  "details": "关键细节（≤100字）",
  "entities": ["相关实体"],
  "domains": ["影响的领域"],
  "source_url": "原文URL",
  "timestamp": "事件发生时间（如果能判断）",
  "significance": 1-5  // 对美伊局势的影响程度
}

文章标题：{title}
文章内容：{content}
```

### 6.2 DAG Engine Prompt（核心 prompt）

```
你是一个地缘政治风险分析师，负责维护一个因果概率网络（DAG）。

## 你的分析工具箱（思维模型）
{mental_models_content}

## 当前 DAG 状态
{current_dag_json}

## 新接收到的事件
{events_json}

## 你的任务

分析新事件对因果网络的影响，输出结构化的更新决策。

### 规则
1. 概率范围 0.0-1.0，保留两位小数
2. DAG 必须无环（不允许循环因果）
3. 每个新节点必须指定 domains（从预定义列表选择）
4. 每条边必须有 reasoning 解释因果关系
5. 概率变化必须有 evidence 支撑
6. 只在有充分理由时才新增节点，避免网络过度膨胀
7. 如果事件不影响任何现有节点且不值得新增节点，输出空更新

### 输出格式（严格 JSON）
{
  "analysis": "整体分析摘要（200字内）",
  "model_insights": [
    { "model": "模型名", "insight": "该模型视角下的洞察" }
  ],
  "updates": {
    "new_nodes": [
      {
        "id": "snake_case_id",
        "label": "中文标签",
        "domains": ["领域1"],
        "probability": 0.5,
        "confidence": 0.7,
        "evidence": ["证据"],
        "reasoning": "为什么新增这个节点"
      }
    ],
    "new_edges": [
      {
        "from": "node_id",
        "to": "node_id",
        "weight": 0.7,
        "reasoning": "因果关系解释"
      }
    ],
    "probability_changes": [
      {
        "node_id": "xxx",
        "new_probability": 0.6,
        "new_confidence": 0.8,
        "evidence": ["新证据"],
        "reasoning": "调整原因"
      }
    ],
    "removed_nodes": [],
    "removed_edges": []
  }
}
```

### 6.3 Reporter Prompt

Reporter 不需要 LLM，用模板引擎生成结构化文本即可。格式见 Section 8。

---

## 7. 数据源

### 7.1 Readwise 订阅推荐（美伊 MVP）

通过 Readwise Reader 订阅以下 RSS 源：

| 源 | RSS | 价值 | 优先级 |
|---|---|---|---|
| **Reuters World News** | reuters.com/world (RSS) | 快速、客观的硬新闻 | P0 |
| **Al Jazeera Middle East** | aljazeera.com/middle-east (RSS) | 中东视角，补充西方盲区 | P0 |
| **War on the Rocks** | warontherocks.com (RSS) | 军事/安全策略深度分析 | P0 |
| **OilPrice.com** | oilprice.com (RSS) | 能源市场+地缘交叉 | P0 |
| **CSIS** | csis.org (RSS) | 美国智库分析 | P1 |
| **Responsible Statecraft** | responsiblestatecraft.org (RSS) | 反干预视角，平衡鹰派 | P1 |
| **Iran International** | iranintl.com (RSS) | 伊朗内部动态（英文） | P1 |
| **The Cradle** | thecradle.co (RSS) | 中东地区深度报道 | P2 |
| **Energy Intelligence** | energyintel.com (RSS) | 能源行业专业分析 | P2 |

### 7.2 数据接入方式

复用 Second Brain 的 Readwise 集成（`ReadwiseClient`）：
- GeoPulse Ingester 调用 Readwise API 拉取新文章
- 用 Readwise 的 tag/folder 机制区分 GeoPulse 订阅和其他订阅
- 建议在 Readwise 中创建 `geopulse` tag 或 folder

### 7.3 数据流水线

```
Readwise Reader
  ↓ (API v3, 增量同步)
Ingester（过滤 geopulse tag 的文章）
  ↓
Analyzer（LLM 提取事件，过滤无关/噪音）
  ↓
DAG Engine（更新概率网络）
```

---

## 8. 报告格式

### 8.1 每日态势报告

```
⚡ GeoPulse 日报 — 美伊态势
━━━━━━━━━━━━━━━━━━━━━━━━━
📅 2026-03-05 | 📊 全局风险: 42/100 (↑3)

📰 关键事件（过去24h，共N篇报告）

▸ [事件1摘要]
▸ [事件2摘要]
▸ [事件3摘要]

🔮 概率变动（变化 ≥5% 的节点）

| 节点 | 概率 | 变化 | 原因 |
|------|------|------|------|
| 霍尔木兹封锁 | 0.25 | ↑8% | 伊朗海军演习 |
| 油价飙升 | 0.30 | ↑5% | 传导自封锁概率上升 |

🌐 因果网络

零阶 ─ 美伊军事冲突(0.35)
一阶 ┬ 霍尔木兹封锁(0.25) [能源/军事]
     ├ 代理人战争升级(0.45) [军事]
     └ 制裁升级(0.60) [政治]
二阶 ┬ 油价飙升(0.30) [能源/金融]
     ├ 航运中断(0.20) [经济]
     └ 能源供应紧张(0.35) [能源]
三阶 ┬ 欧洲电力涨价(0.25) [能源/经济]
     └ 通胀加剧(0.20) [经济]
四阶 ─ 数据中心成本(0.15) [科技/经济]

🧠 思维模型洞察

▸ [威慑理论] 美国航母部署提高打击可信度，但伊朗的
  不对称反击能力（导弹+代理人）构成有效反威慑
▸ [反事实] 若无近期核谈判破裂，冲突概率约低15%

📈 投资关注

▸ WTI 期货受影响概率: 0.30 (二阶)
▸ 黄金避险: 0.45 (一阶)
▸ 关注链条: 封锁→油价→欧洲电力→数据中心成本
```

### 8.2 按需查询响应

用户可以问：
- "某个节点的详情" → 展示节点概率、证据、关联的上下游
- "某条传导链" → 展示完整因果路径和各节点概率
- "某个领域的风险" → 展示该领域所有节点
- "和昨天比有什么变化" → 对比两个快照

---

## 9. 存储设计

### 9.1 文件结构

```
~/Projects/geopulse/
├── src/
│   └── geopulse/
│       ├── __init__.py
│       ├── ingester.py        # Readwise 数据拉取
│       ├── analyzer.py        # LLM 事件提取
│       ├── dag_engine.py      # DAG 管理 + LLM 更新
│       ├── propagator.py      # 概率传导计算
│       ├── reporter.py        # 报告生成
│       └── models.py          # 数据模型（Node, Edge, DAG）
├── models/                    # 思维模型库
│   ├── counterfactual.md
│   ├── deterrence.md
│   ├── brinkmanship.md
│   ├── focal_points.md
│   ├── second_order.md
│   ├── fog_of_war.md
│   ├── sunk_cost_escalation.md
│   └── asymmetric_conflict.md
├── data/                      # 运行时数据（gitignore）
│   ├── dag.json               # 当前 DAG 状态
│   ├── events.jsonl           # 事件日志
│   └── history/               # DAG 历史快照
│       └── 2026-03-05T140000.json
├── configs/
│   ├── config.yaml            # 项目配置
│   └── sources.yaml           # Readwise 数据源配置
├── tests/
│   └── ...
├── docs/
│   └── plans/
│       └── 2026-03-05-geopulse-design.md  # 本文档
├── pyproject.toml
└── .env                       # READWISE_TOKEN, ANTHROPIC_API_KEY
```

### 9.2 DAG 持久化

- `data/dag.json` — 当前 DAG 的完整状态，每次更新覆写
- `data/history/{timestamp}.json` — 每次更新前保存快照，用于：
  - 概率变化趋势追踪
  - 报告生成时对比前后差异
  - 调试和回溯
- 保留最近 30 天的快照，更早的自动清理

### 9.3 事件日志

`data/events.jsonl` — append-only 日志，每行一个事件 JSON：

```json
{"timestamp": "2026-03-05T14:00:00+08:00", "headline": "...", "details": "...", "source_url": "...", "dag_version": 12}
```

---

## 10. OpenClaw Agent 配置

### 10.1 Agent 定义

在 `openclaw.json` 的 agents 中添加 GeoPulse agent：

```json
{
  "name": "geopulse",
  "label": "GeoPulse",
  "description": "地缘政治概率传导追踪系统",
  "model": { "provider": "anthropic", "model": "claude-sonnet-4-6" },
  "systemPrompt": "你是 GeoPulse，一个地缘政治风险分析 agent...",
  "tools": ["readwise", "dag_update", "dag_query", "report"],
  "schedule": {
    "daily_report": { "cron": "0 9 * * *", "action": "generate_daily_report" }
  }
}
```

注意：具体的 OpenClaw agent 配置格式需参考 OpenClaw 文档，以上为概念示意。

### 10.2 Telegram 交互

复用 OpenClaw 的 Telegram 通道。用户可以通过消息与 GeoPulse 对话：

- `@geopulse 日报` → 手动触发日报
- `@geopulse 霍尔木兹封锁` → 查询该节点详情
- `@geopulse 能源链条` → 查看能源领域传导链
- `@geopulse 对比昨天` → 查看概率变化

---

## 11. 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | DT 偏好，和 Second Brain 一致 |
| LLM | Claude Sonnet 4.6 | 性价比高，Opus 用于复杂分析时切换 |
| 存储 | JSON 文件 | MVP 够用，无需数据库 |
| 概率模型 | Noisy-OR | 简单有效，不需要完整贝叶斯推断 |
| 思维模型注入 | 全量注入 | MVP 模型少，全部给 LLM 参考 |
| 调度 | OpenClaw 内置 | 复用现有基础设施 |
| 通信 | Telegram via OpenClaw | 复用现有通道 |

---

## 12. 未来扩展（不在 MVP 范围内）

1. **多场景支持**：中美博弈、俄乌、台海等，每个场景一个独立 DAG
2. **跨场景传导**：不同场景的 DAG 之间建立连接（如中东冲突影响中美关系）
3. **Second Brain 联动**：概率变化触发 signal_engine 的交易信号
4. **选择性模型注入**：按事件类型匹配思维模型，减少 token 消耗
5. **可视化**：生成 DAG 图片（graphviz/mermaid）附在 Telegram 消息中
6. **回测**：用历史新闻回测概率预测的准确性
7. **市场数据融合**：接入价格数据，将市场反应作为验证信号

---

## 附录 A：思维模型详细设计

### A.1 反事实推理 (Counterfactual Thinking)

**核心问题**：如果某个事件没有发生，概率网络会怎样？

**分析框架**：
1. 选定要移除的事件（假设它没发生）
2. 重新评估直接关联的节点概率
3. 沿 DAG 传导，计算整体影响
4. 差值 = 该事件的"因果贡献"

**应用场景**：评估单一事件的真实影响力，避免概率叠加时高估。

### A.2 威慑理论 (Deterrence Theory)

**来源**：Thomas Schelling, *The Strategy of Conflict*

**核心问题**：威胁是否可信？承诺是否绑定？

**分析框架**：
1. 威胁方的能力（capability）
2. 威胁的可信度（credibility）— 执行成本 vs 不执行的声誉损失
3. 对方的退出选项（off-ramps）
4. 观众成本（audience cost）— 公开承诺后退缩的政治代价

### A.3 边缘策略 (Brinkmanship)

**来源**：Thomas Schelling

**核心问题**：升级到什么程度会停？双方的红线在哪？

**分析框架**：
1. 当前在"悬崖"上的位置
2. 双方对"坠崖"后果的认知
3. 控制权是否仍在双方手中（vs 意外升级风险）
4. 历史先例中类似博弈的结果

### A.4 焦点理论 (Focal Points / Schelling Points)

**来源**：Thomas Schelling

**核心问题**：在没有明确沟通的情况下，双方会在哪个点协调？

**分析框架**：
1. 文化/历史上的"自然"停止点
2. 地理边界（如停火线）
3. 国际规范/先例
4. 媒体和公众预期形成的焦点

### A.5 二阶效应 (Second-Order Effects)

**核心问题**：各方对事件的反应是什么？反应的反应又是什么？

**分析框架**：
1. 直接利益相关方的反应
2. 间接利益相关方的反应
3. 市场参与者的预期和行为
4. 反馈循环（正反馈=升级，负反馈=稳定）

### A.6 雾中决策 (Fog of War)

**核心问题**：信息的可靠性如何？决策者在信息不完整下会犯什么错？

**分析框架**：
1. 信息来源的可信度
2. 决策者面临的认知偏差
3. 误判/误读风险
4. 信息延迟导致的反应滞后

### A.7 沉没成本与承诺升级 (Sunk Cost Escalation)

**核心问题**：已有投入是否会推动不理性的持续升级？

**分析框架**：
1. 双方已投入的政治资本/军事资源/声誉
2. 止损退出的成本 vs 继续加码的成本
3. 国内政治压力对退出的阻碍
4. "赢一把回本"心理

### A.8 不对称冲突 (Asymmetric Conflict)

**核心问题**：弱方如何利用非对称手段改变博弈？

**分析框架**：
1. 实力对比和弱方的优势领域
2. 弱方的非对称手段（恐怖主义、网络攻击、代理人、经济制裁反击）
3. 强方的脆弱点
4. 时间因素（弱方是否能拖延到强方失去耐心）
