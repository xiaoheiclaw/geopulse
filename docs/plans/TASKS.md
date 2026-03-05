# GeoPulse Implementation Tasks

> 进度追踪。接手时从第一个未完成的任务开始。
> 实现计划详见 `2026-03-05-geopulse-implementation.md`

## 状态

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| 1 | Project Scaffold (pyproject.toml, config, .gitignore) | [x] | |
| 2 | Data Models — Node, Edge, Event, DAG (Pydantic) | [x] | 15 tests |
| 3 | Propagator — Noisy-OR 概率传导 | [x] | 5 tests |
| 4 | Mental Models Library — 8 个思维模型 .md + loader | [x] | 4 tests |
| 5 | DAG Persistence — save/load/history 快照 | [x] | 5 tests |
| 6 | Ingester — Readwise API + tag 过滤 | [x] | 3 tests |
| 7 | Analyzer — LLM 事件提取 | [x] | 3 tests |
| 8 | DAG Engine — LLM 更新 + 环检测 | [x] | 3 tests |
| 9 | Reporter — 日报 + 节点详情 | [x] | 4 tests |
| 10 | Pipeline + CLI — 全流程编排 | [x] | 2 tests |
| 11 | OpenClaw Agent Workspace — SOUL.md, openclaw.json | [x] | workspace-geopulse |
| 12 | Integration Test — 端到端 mock 测试 | [x] | 1 e2e test |
| 13 | Push to GitHub — xiaoheiclaw/geopulse | [x] | https://github.com/xiaoheiclaw/geopulse |

## 执行方式

每个任务按 TDD 流程：写测试 → 跑失败 → 写实现 → 跑通过 → commit

## 依赖关系

```
1 (scaffold)
├── 2 (models)
│   ├── 3 (propagator)
│   ├── 5 (storage)
│   ├── 7 (analyzer)
│   └── 8 (dag engine) ← 依赖 4 (mental models)
├── 4 (mental models)
├── 6 (ingester)
├── 9 (reporter) ← 依赖 2
├── 10 (pipeline) ← 依赖 2-9 全部
├── 11 (openclaw) ← 独立，可并行
├── 12 (integration) ← 依赖 10
└── 13 (push) ← 最后
```
