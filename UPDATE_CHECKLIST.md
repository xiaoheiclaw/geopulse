# 更新清单 — GeoPulse 每轮数据刷新

每次抓取新闻/更新数据时，按顺序执行以下步骤。

## 1. 采集新闻
- [ ] Web search: 冲突最新进展
- [ ] Web search: 油价/市场数据
- [ ] Web search: 海峡/航运状态
- [ ] Web search: 核/IAEA/升级信号
- [ ] 如有重大新信号，额外搜索专题

## 2. DAG 节点概率更新 (`data/dag.json`)
- [ ] Event 节点：新事件→新增 Event 节点 (100%)
- [ ] State 节点：当前状态有无变化？逐个审查：
  - `hormuz_blockade` — 封锁程度变了吗？
  - `supply_disruption_volume` — 中断量变了吗？
  - `supply_offset_capacity` — 替代供应有新动作？(SPR释放？增产？)
  - `shipping_insurance_collapse` — 保险费率变化？
  - `iran_missile_degraded` — 新战损评估？IRGC还在发射？
  - `regional_spillover` — 新的国家/地区被卷入？
  - `iran_power_transition` — 继位有新进展？
  - `coalition_forming` — 新国家加入联盟？
  - `russia_energy_leverage` — 俄罗斯有新动作？
  - `energy_crisis` — IEA有新声明？
  - `secondary_sanctions` — 新制裁宣布？
  - `input_inflation_transmission` — PPI/CPI新数据？
  - `em_capital_outflow` — 资金流数据？
  - `earnings_downgrade` — 华尔街有下修？
- [ ] Prediction 节点：从 State 变化级联推算
- [ ] **每个更新必须附 evidence 来源**
- [ ] **检查衰减**：任何调整后，确认传导链逐级衰减合理
- [ ] 更新 `dag.version` + `dag.updated`

## 3. 场景权重更新 (`data/runs/run_*.json`)
- [ ] 四个场景逐个评估，新证据是否改变权重：
  - 持久消耗战 (当前 45%)
  - 快速升级至核门槛 (当前 25%)
  - 碎片化代理人战争 (当前 22%)
  - 外交斡旋降级 (当前 8%)
- [ ] 权重之和 = 100%
- [ ] 设置 `weight_prev` 以便看板显示变化量

## 4. 瓶颈节点审查
- [ ] 瓶颈排序有无变化？(path_importance)
- [ ] 有没有新的瓶颈出现？

## 5. 触发器检查
- [ ] 现有触发器是否被触发？(如 Brent>$100, IAEA异常)
- [ ] 需不需要新增触发器？

## 6. SHS 假说检查 (`data/shs.json`)
- [ ] 现有假说置信度是否需要调整？
- [ ] 有假说被证实/证伪？
- [ ] 需不需要新增假说？

## 7. 构建 + 推送
- [ ] `python scripts/build_dashboard.py` — 重建看板
- [ ] `git add -A && git commit && git push` — 推送
- [ ] 看板确认可访问

## 8. 报告更新 (`docs/report_YYYYMMDD.md`)
- [ ] 概率表更新 (含 vs 上版变化列)
- [ ] 传导链数字更新
- [ ] 新信号写入"今日最重磅"
- [ ] 仓位逻辑是否需要调整？
- [ ] 盲区/Pre-Mortem 有新发现？
- [ ] 触发器列表更新
- [ ] git push 报告

## 9. 红队审计 (每2-3轮跑一次)
- [ ] 0 cycles
- [ ] 0 orphans
- [ ] 所有节点有阈值定义
- [ ] 低衰减边 < 15条
- [ ] 叶子节点 < 30%

## 10. Memory
- [ ] 更新 `memory/YYYY-MM-DD.md` — 记录本轮关键变化
- [ ] 如有重大设计决策，更新 `MEMORY.md`

---

## 推送规则

| 优先级 | 触发条件 | 动作 |
|--------|---------|------|
| P0 | 任意节点概率变化 ≥20% | 立即推送到 Discord |
| P1 | 概率变化 ≥10% 或新增关键节点 | Heartbeat 汇总推送 |
| P2 | 常规更新无显著变化 | 仅记录，不推送 |

## 当前基线 (v26, 2026-03-07 10:40)

```
封锁 90% → 中断 85% → 缺口 78% → 危机 72% → Brent 72%
→ 通胀 62% → 滞胀 45% → Fed 52% → 美债 48% → EM外流 55% → EM危机 42%

场景: 消耗45% / 核25% / 代理人22% / 外交8%
```
