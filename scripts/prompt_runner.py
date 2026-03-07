#!/usr/bin/env python3
"""
GeoPulse LLM Prompt Runner — 调用 API 执行 prompt 库中的模板。

用法:
  # 事件提取
  python scripts/prompt_runner.py p1 "Russia providing targeting intel to Iran..."

  # 证据评级
  python scripts/prompt_runner.py p3 "WaPo reports citing anonymous officials..."

  # 辩证质疑 (无额外输入)
  python scripts/prompt_runner.py p4

  # 从文件读取输入
  python scripts/prompt_runner.py p1 --file news.txt

  # 保存输出
  python scripts/prompt_runner.py p1 "..." --save
"""

import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Anthropic API via relay
try:
    import anthropic
except ImportError:
    print("pip install anthropic")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def get_client():
    """Create Anthropic client using .env config."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    base = os.environ.get("ANTHROPIC_BASE_URL", "https://ai-relay.chainbot.io")
    # SDK appends /v1 automatically; don't double it
    if base.endswith("/v1"):
        base = base[:-3]
    return anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=base,
    )


def load_dag_summary():
    """Load DAG and create a compact summary for prompts."""
    dag = json.load(open(DATA_DIR / "dag.json"))
    nodes = dag["nodes"]

    lines = []
    for nid, n in sorted(nodes.items(), key=lambda x: -x[1]["probability"]):
        lines.append(f"{nid}: {n['label']} [{n['node_type']}] {n['probability']:.0%}")
    return "\n".join(lines)


def load_dag_full():
    """Load full DAG JSON (for P4)."""
    return json.dumps(json.load(open(DATA_DIR / "dag.json")), ensure_ascii=False)


def load_latest_run():
    runs_dir = DATA_DIR / "runs"
    runs = [f for f in runs_dir.iterdir() if f.suffix == ".json"]
    if not runs:
        return None
    runs.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return json.load(open(runs[0]))


# ═══════════════════════════════════════════
# Prompt Builders
# ═══════════════════════════════════════════

def build_p1(news_text: str) -> str:
    """P1: 事件提取"""
    dag_summary = load_dag_summary()

    return f"""# 角色
你是 GeoPulse 事件提取器。你的任务是把非结构化新闻转化为对贝叶斯因果网络(DAG)的结构化影响判断。

# 认知纪律
1. **先反后正**：对每个你认为的影响方向，先用30字论证相反方向，再决定
2. **区分信号和噪音**：问自己"如果这条新闻没发生，我的判断会不同吗？"如果答案是"差不多"，这是噪音
3. **避免锚定**：不要被数字锚定。"涨8%"感觉很大，但要问"相对于历史波动率是几个sigma？"
4. **因果不等于相关**

# ⚠ 关键约束：你不输出具体概率数字
你只判断：方向(up/down) + 量级(negligible/minor/moderate/significant/dramatic)
具体的概率delta由下游校准代码计算。你不需要也不应该猜"+12%"这种数字。

# 量级定义
- **negligible**: 预期内消息，对概率无实质影响
- **minor**: 预期内但有增量信息，轻微调整
- **moderate**: 超预期，改变某个子环节的判断
- **significant**: 改变博弈结构或因果链的判断
- **dramatic**: 黑天鹅级别，颠覆核心假设
绝大多数日常新闻是 negligible 或 minor。significant 应该很少见。dramatic 极罕见。

# 似然比思维
对每个影响，你需要回答：
- P(E|H): 如果该节点代表的事件/状态确实发生，出现这条新闻的概率有多大？
- P(E|¬H): 如果该节点不发生，出现这条新闻的概率有多大？
- 似然比 = P(E|H) / P(E|¬H)。似然比>1说明新闻支持H，<1说明新闻反对H
给出似然比估计（不需要精确，给范围即可：1-2弱证据 / 2-5中等 / 5-10强 / >10极强）

# 多阶传导
不要只标注一阶。A→B→C至少追到第3阶。注意：高阶传导的量级应比前一阶降一级（significant→moderate→minor）。

# 输出格式（严格JSON）
{{
  "headline": "一句话标题",
  "source_credibility": 0.0-1.0,
  "impacts": [
    {{
      "node_id": "existing_node_id",
      "direction": "up|down|unchanged",
      "magnitude": "negligible|minor|moderate|significant|dramatic",
      "likelihood_ratio": "1-2|2-5|5-10|>10",
      "transmission_order": 1,
      "mechanism": "传导机制",
      "counter_argument": "反方向论证",
      "confidence": 0.0-1.0
    }}
  ],
  "contradicts_current_thesis": false,
  "new_node_suggestion": null,
  "noise_flag": false,
  "noise_reasoning": ""
}}

# 当前DAG节点
{dag_summary}

# 新闻
{news_text}"""


def build_p3(evidence_text: str) -> str:
    """P3: 证据可信度评估"""
    return f"""# 角色
你是GeoPulse证据评估员。评估信息来源的可信度。

# 评分维度
1. 来源层级: 一手(0.9基础) / 二手(0.7) / 三手(0.4)
2. 交叉验证: 3+源+0.15 / 2源+0.10 / 单源+0.00 / 矛盾-0.10
3. 来源偏见: 中性+0.00 / 已知偏见-0.05 / 明确立场-0.15 / 交战方战果-0.25
4. 具体性: 精确可验证+0.10 / 有细节+0.00 / 模糊-0.10
5. 时效: <6h+0.05 / 6-24h+0.00 / 24-72h-0.05 / >72h-0.10

# 输出格式（严格JSON）
{{
  "evidence_text": "原文摘要",
  "source": "来源",
  "source_tier": 1|2|3,
  "cross_verification_count": 0,
  "bias_assessment": "neutral|mild|strong|adversarial",
  "specificity": "precise|detailed|vague",
  "hours_old": 0,
  "score_breakdown": {{
    "base": 0.7,
    "cross_verify": 0.0,
    "bias": 0.0,
    "specificity": 0.0,
    "timeliness": 0.0
  }},
  "final_score": 0.7,
  "usable": true,
  "reasoning": "一句话"
}}

# 证据
{evidence_text}"""


def build_p4() -> str:
    """P4: 辩证质疑"""
    dag_json = load_dag_full()
    run = load_latest_run()
    run_json = json.dumps(run, ensure_ascii=False)[:3000] if run else "{}"

    return f"""# 角色
你是GeoPulse红队审计员。你是分析师的对手。你的唯一KPI是找到错误。

# ⚠ 关键约束：你不输出具体概率数字或权重数字
你只判断：当前概率/权重是偏高(overestimated)、偏低(underestimated)、还是合理(fair)。
如果偏了，给出偏离程度：slight(差一个量级内) / moderate(差1-2个量级) / strong(差2个量级以上)。
具体数字由校准代码计算。

# 任务
1. 高概率节点反论(>60%每一个): 构造NOT发生的最可信场景，引用历史先例
   - 判断: overestimated / underestimated / fair
   - 偏离: slight / moderate / strong
2. 高权重边质疑(>0.7每一条): 找A发生但B没发生的案例
   - 判断: overestimated / underestimated / fair
   - 偏离: slight / moderate / strong
3. 隐含假设(恰好3个)
4. 缺失节点(恰好3个)
5. 做空论据(恰好5个，每个有可验证预测)
6. 自我评估(1-10分)

影响仓位的错误用 🚨 标注。
输出JSON。

# DAG
{dag_json[:8000]}

# RunOutput (摘要)
{run_json}"""


# ═══════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════

MODELS = {
    "primary": "claude-opus-4-6",
    "fallback": "claude-opus-4-5-20251101",
    "fast": "claude-sonnet-4-6",
}


def call_llm(prompt: str, model: str = MODELS["primary"], max_tokens: int = 8000) -> str:
    """Call Anthropic API with automatic fallback."""
    client = get_client()
    
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=90.0,
        )
        return response.content[0].text
    except Exception as e:
        if model == MODELS["primary"]:
            fb = MODELS["fallback"]
            print(f"⚠️  {model} failed ({type(e).__name__}), falling back to {fb}...")
            return call_llm(prompt, model=fb, max_tokens=max_tokens)
        raise


def save_result(prompt_id: str, result: str):
    """Save prompt result to data/prompt_results/."""
    out_dir = DATA_DIR / "prompt_results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{prompt_id}_{ts}.json"

    # Try to parse as JSON, save raw if not
    try:
        parsed = json.loads(result)
        with open(out_path, "w") as f:
            json.dump({"prompt_id": prompt_id, "timestamp": ts, "result": parsed}, f, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        with open(out_path, "w") as f:
            json.dump({"prompt_id": prompt_id, "timestamp": ts, "raw": result}, f, indent=2, ensure_ascii=False)

    print(f"Saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="GeoPulse Prompt Runner")
    parser.add_argument("prompt_id", choices=["p1", "p3", "p4"], help="Prompt to run")
    parser.add_argument("text", nargs="?", default="", help="Input text")
    parser.add_argument("--file", help="Read input from file")
    parser.add_argument("--save", action="store_true", help="Save result to data/prompt_results/")
    parser.add_argument("--model", default=MODELS["primary"])
    args = parser.parse_args()

    # Input text
    text = args.text
    if args.file:
        text = Path(args.file).read_text()

    # Build prompt
    if args.prompt_id == "p1":
        if not text:
            print("ERROR: P1 requires news text input")
            sys.exit(1)
        prompt = build_p1(text)
    elif args.prompt_id == "p3":
        if not text:
            print("ERROR: P3 requires evidence text input")
            sys.exit(1)
        prompt = build_p3(text)
    elif args.prompt_id == "p4":
        prompt = build_p4()
    else:
        print(f"Unknown prompt: {args.prompt_id}")
        sys.exit(1)

    # Call LLM
    print(f"Calling {args.model}...")
    result = call_llm(prompt, model=args.model)
    print(result)

    if args.save:
        save_result(args.prompt_id, result)


if __name__ == "__main__":
    main()
