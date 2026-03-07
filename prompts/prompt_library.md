# GeoPulse Prompt 库

所有需要 LLM 推理的环节，固化 prompt 模板。
脚本管规则，prompt 管语义。

---

## P1: 事件提取（每次新闻输入时）

```
你是GeoPulse事件提取器。从以下新闻中提取结构化的DAG影响。

对每条新闻：
1. **affected_nodes**: 受影响的节点ID列表
2. **direction**: 每个节点的概率应该 ↑上调 还是 ↓下调
3. **magnitude**: 幅度估计（微调<3% / 中等3-10% / 显著>10%）
4. **confidence**: 你对这条判断的信心（0-1）
5. **reasoning**: 一句话解释传导机制
6. **new_node_needed**: 如果现有节点无法捕捉这条新闻的影响，建议新增什么节点

输出JSON数组。

当前DAG节点列表:
{node_id_list_with_labels}

新闻输入:
{news_text}
```

### 使用时机
- 每次DT贴新闻或heartbeat采集到新信息

### 输出处理
- affected_nodes + direction + magnitude → 人工确认后更新 dag.json
- new_node_needed → Phase 4 Graph Proposal 流程
- 记入 data/events.jsonl

---

## P2: 场景Wargame（场景权重更新时）

```
你是GeoPulse场景推演员。对当前四个场景进行兵棋推演。

当前场景及权重:
{scenarios_with_weights}

当前关键状态:
{key_states_summary}

最新事件:
{recent_events}

对每个场景：
1. **next_3_moves**: 如果走这个场景，未来2周各方（美国/伊朗/俄罗斯/以色列）最可能的3步棋
2. **enablers**: 哪些条件需要满足，这个场景才会实现？
3. **blockers**: 哪些因素在阻止这个场景？
4. **weight_assessment**: 基于当前证据，你认为这个场景的权重应该是多少？（给出理由）
5. **surprise_scenario**: 有没有第5个你没考虑的场景？

约束：
- 四个场景权重之和 = 100%
- 如果你的评估和当前权重偏差>5%，必须给出具体证据
- 考虑受众成本（退出的政治代价）
```

### 使用时机
- 每次重大事件后（P0/P1级别变化）
- 至少每2天跑一次

### 输出处理
- weight_assessment → 对比当前权重，偏差>5%时提示人工审核
- surprise_scenario → 评估是否需要第5个场景
- next_3_moves → 记入 RunOutput.horizon_theses

---

## P3: 证据可信度评估（新证据入库时）

```
你是GeoPulse证据评估员。评估以下信息来源的可信度。

对每条证据：
1. **source_type**: 一手(卫星/官方声明/财报) / 二手(媒体报道) / 三手(分析师观点/社交媒体)
2. **cross_verification**: 有几家独立来源报道了同一事实？
3. **source_bias**: 来源方有没有动机歪曲？（例：伊朗官方媒体报己方战果）
4. **specificity**: 信息是具体可验证的（"Brent $92.69"）还是模糊的（"油价大涨"）？
5. **timeliness**: 信息有多新鲜？（<1h / <24h / >24h）
6. **credibility_score**: 综合可信度 0.0-1.0
7. **reasoning**: 一句话评估

可信度锚点:
- 0.95+: 多家权威来源交叉验证的硬数据（Reuters+Bloomberg+官方）
- 0.80: 单一权威来源的一手报道（WaPo引述匿名官员）
- 0.60: 单一来源二手报道，无交叉验证
- 0.40: 分析师推测/社交媒体/匿名信源
- 0.20: 未经证实的传言/宣传材料

证据:
{evidence_list}
```

### 使用时机
- 每条新证据入 evidence 列表前

### 输出处理
- credibility_score → 写入 Node.evidence 的元数据
- score < 0.4 的证据 → 标记 "unverified"，不直接影响概率
- 如果节点的所有证据都 < 0.6 → 红队 warning

---

## P4: 红队辩证质疑（DAG更新后）

```
你是GeoPulse红队审计员。你的唯一任务是找出下面这个因果网络(DAG)中的逻辑错误、隐含假设和盲区。

规则：
1. 对每个概率>60%的预测节点，构造一个它NOT发生的可信场景
2. 对每条权重>0.7的因果边，质疑"为什么A一定导致B？有没有A发生但B不发生的反例？"
3. 列出DAG中最大的3个隐含假设（你觉得分析者没说出来但暗含了的前提）
4. 列出DAG中缺失的最重要的3个节点（应该在图里但不在的因素）
5. 如果你是做空我们核心thesis（能源冲击→滞胀→EM危机）的对冲基金，你的5个最强论据是什么？

{dag_json}
{run_output_json}
```

### 使用时机
- 每次DAG更新后

---

## P5: Pre-Mortem（每周一次）

```
假设现在是2026年9月（6个月后），回头看GeoPulse在2026年3月的分析，结果完全错了——我们的核心场景没有发生。

1. 最可能的原因是什么？（列出3-5个）
2. 哪个节点的概率偏差最大？为什么？
3. 我们遗漏了哪条关键因果链？
4. 哪些"不可能"的事情其实发生了？
5. 如果让你重新设计这个DAG，你会做什么不同？

当前DAG状态:
{dag_summary}

当前核心thesis:
{thesis_summary}
```

### 使用时机
- 每周一次

---

## P6: Fearon受众成本（停火/升级信号时）

```
分析以下冲突中各方的受众成本结构（退出的政治代价）:

对于每一方(美国Trump/伊朗IRGC/以色列Netanyahu/俄罗斯Putin):
1. 如果现在退出/停火，该领导人面临的国内政治成本是什么？
2. 承诺是否已锁定？(公开声明、立法投票、军事部署)
3. 有没有"体面退出"的路径？
4. 退出成本的非对称性：谁退出代价更高？
5. 对这个DAG中ceasefire_backchannel和conflict_deescalation的概率，你认为该上调还是下调？为什么？

当前概率:
{ceasefire_probs}
```

### 使用时机
- 停火/升级信号出现时

---

## 集成方式

每个 prompt 的输出都要经过三步:
1. **LLM 生成** → 结构化 JSON 输出
2. **脚本验证** → 检查格式、范围、一致性
3. **人工确认** → DT 审批后才写入 DAG

不存在 LLM 直接修改 DAG 的路径。所有修改都经过人。
