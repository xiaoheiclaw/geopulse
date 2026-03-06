import { useState, useMemo } from "react";

/*
  GeoPulse v7.4 Terminal
  Three orthogonal axes + Registry Constitution
  - Pipeline: 做什么 (fixed)
  - Memory: 关注什么 (learnable)
  - Registry: 怎么想 (pluggable, governed)
*/

const LAYERS = [
  { id: "L1", name: "证据归一化", en: "Evidence Normalization", color: "#818cf8", task: "压缩信息流为标准化证据", group: "pre" },
  { id: "L2a", name: "分支定义", en: "Scenario Framing", color: "#a78bfa", task: "生成/维护状态分支与质疑性检验", group: "pre" },
  { id: "L2b", name: "瓶颈提取", en: "Bottleneck Extraction", color: "#c084fc", task: "抽出 Regime 关键节点 → 三因子聚合", group: "pre" },
  { id: "L3", name: "结构传播", en: "Structural Propagation", color: "#3b82f6", task: "M/H基线: 非策略性因果传导", group: "engine", regime: "A" },
  { id: "L3.5", name: "策略求解", en: "Strategic Resolution", color: "#f59e0b", task: "S/H修正: Pipeline 按需从 Registry 加载模型", group: "engine", regime: "B" },
  { id: "L4", name: "期限映射", en: "Horizon Translation", color: "#fbbf24", task: "分支权重/均衡路径 → 分窗口交易命题", group: "post" },
  { id: "L5", name: "执行监控", en: "Execution & Monitor", color: "#10b981", task: "仓位 · 触发器 · 失效条件", group: "post" },
];

const MODELS = [
  { id: "schelling-focal", name: "Schelling Focal Point", cat: "博弈论", layers: ["L2a", "L3.5", "L4"], color: "#f59e0b",
    input: "玩家集合 + 均衡候选", output: "筛选后主均衡 + 置信度",
    callable: "Pipeline 在均衡求解时发现多个候选",
    scope: "多均衡博弈; 不适用于单一传导链",
    role: "P", cost: "medium" },
  { id: "schelling-commit", name: "Schelling Commitment", cat: "博弈论", layers: ["L3.5", "L2b"], color: "#f59e0b",
    input: "玩家承诺 + 退路 + 受众", output: "承诺可信度三维评分",
    callable: "节点涉及公开承诺/红线声明",
    scope: "主权博弈/外交承诺; 不适用于企业运营",
    role: "P", cost: "medium" },
  { id: "perez", name: "Carlota Perez", cat: "长周期", layers: ["L2a"], color: "#c084fc",
    input: "技术扩散 + 金融泡沫信号", output: "技术革命阶段判定",
    callable: "分支涉及技术范式转换",
    scope: "长周期技术-金融耦合; 不适用于短期危机",
    role: "P", cost: "light" },
  { id: "dialectic", name: "辩证质疑", cat: "认知纪律", layers: ["L2a", "L3.5"], color: "#a78bfa",
    input: "任意判断/分支", output: "Thesis + Antithesis + 修正",
    callable: "核心纪律: 每轮分支生成时自动请求",
    scope: "通用; 无边界限制",
    role: "D", cost: "light" },
  { id: "nth-order", name: "N阶推演", cat: "传导分析", layers: ["L3", "L3.5"], color: "#3b82f6",
    input: "冲击事件 + 传导图谱", output: "多阶效应链 + 衰减系数",
    callable: "新冲击进入系统, Pipeline 请求传导展开",
    scope: "因果链分析; 不适用于纯策略性节点",
    role: "P", cost: "medium" },
  { id: "fearon", name: "Fearon Audience Cost", cat: "博弈论", layers: ["L3.5", "L2b"], color: "#f59e0b",
    input: "领导人类型 + 国内政治", output: "退出成本函数 + 升级概率",
    callable: "节点涉及主权博弈且 NCC 评分高",
    scope: "国际危机; 不适用于市场微观结构",
    role: "P", cost: "heavy" },
  { id: "taleb", name: "Taleb 反脆弱", cat: "风险框架", layers: ["L2a", "L5"], color: "#ef4444",
    input: "当前框架假设集", output: "黑天鹅清单 + 凸性暴露",
    callable: "框架更新完成后 + 仓位审计周期",
    scope: "尾部风险; 不适用于基线概率估计",
    role: "D", cost: "medium" },
  { id: "bayes", name: "Bayesian Updating", cat: "概率引擎", layers: ["L1", "L3"], color: "#3b82f6",
    input: "先验 + 新证据", output: "后验概率分布",
    callable: "Regime A 下默认计算范式",
    scope: "概率推断; Regime B 下降为辅助",
    role: "P", cost: "light" },
  { id: "premortem", name: "Pre-Mortem", cat: "认知纪律", layers: ["L2a", "L4"], color: "#a78bfa",
    input: "主分支判断", output: "逆推失败原因清单",
    callable: "高置信度分支(>75%)时 Pipeline 强制请求",
    scope: "决策审计; 不适用于数据处理层",
    role: "D", cost: "light" },
  { id: "toc", name: "Theory of Constraints", cat: "系统分析", layers: ["L2b", "L3"], color: "#10b981",
    input: "系统节点图谱", output: "瓶颈识别 + 杠杆点",
    callable: "分析供应链/产能/流动性场景",
    scope: "系统瓶颈; 不适用于纯博弈节点",
    role: "P", cost: "light" },
];

const CATEGORIES = [...new Set(MODELS.map(m => m.cat))];
const CC = { "博弈论": "#f59e0b", "长周期": "#c084fc", "认知纪律": "#a78bfa", "传导分析": "#3b82f6", "风险框架": "#ef4444", "概率引擎": "#3b82f6", "系统分析": "#10b981" };

function VArr({ c1, c2 }) {
  return (
    <div style={{ display: "flex", justifyContent: "center" }}>
      <svg width="10" height="12" viewBox="0 0 10 12">
        <line x1="5" y1="0" x2="5" y2="8" stroke={c1 || "#334155"} strokeWidth="1" strokeOpacity="0.3" />
        <path d="M2,7 L5,11 L8,7" fill="none" stroke={c2 || c1 || "#334155"} strokeWidth="1" strokeOpacity="0.3" />
      </svg>
    </div>
  );
}

function LRow({ layer, dim, primary, hl, hlColor, hlName }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "36px 1fr", gap: 5,
      padding: "3px 0", opacity: dim ? 0.3 : 1, transition: "opacity 0.4s",
    }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: 10, fontWeight: 800, color: layer.color, textShadow: primary ? `0 0 8px ${layer.color}44` : "none" }}>{layer.id}</div>
        {primary && <div style={{ fontSize: 5.5, color: layer.color, letterSpacing: 0.8, marginTop: 1 }}>主引擎</div>}
      </div>
      <div style={{
        background: hl ? `${hlColor}0c` : "#0c0e18", borderRadius: 5, padding: "5px 8px",
        borderLeft: `2.5px solid ${layer.color}${dim ? "44" : ""}`,
        borderRight: hl ? `2px solid ${hlColor}33` : "2px solid transparent",
        transition: "all 0.3s",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginBottom: 1 }}>
          <span style={{ fontSize: 9.5, fontWeight: 700, color: "#e2e8f0" }}>{layer.name}</span>
          <span style={{ fontSize: 7.5, color: "#475569" }}>{layer.en}</span>
        </div>
        <div style={{ fontSize: 7.5, color: "#64748b", lineHeight: 1.4 }}>{layer.task}</div>
        {hl && <div style={{ marginTop: 2, fontSize: 6.5, color: hlColor, fontWeight: 600 }}>← {hlName}</div>}
      </div>
    </div>
  );
}

export default function GeoPulseV74() {
  const [regime, setRegime] = useState("A");
  const [selModel, setSelModel] = useState(null);
  const [filterCat, setFilterCat] = useState(null);
  const [showConstitution, setShowConstitution] = useState(true);
  const isB = regime === "B";

  const filtered = useMemo(() => filterCat ? MODELS.filter(m => m.cat === filterCat) : MODELS, [filterCat]);
  const selObj = selModel ? MODELS.find(m => m.id === selModel) : null;
  const hlLayers = selObj?.layers || [];

  const pre = LAYERS.filter(l => l.group === "pre");
  const eng = LAYERS.filter(l => l.group === "engine");
  const post = LAYERS.filter(l => l.group === "post");

  const rL = (layer, i, arr) => {
    const dim = (layer.regime === "A" && isB) || (layer.regime === "B" && !isB);
    const pri = (layer.regime === "A" && !isB) || (layer.regime === "B" && isB);
    const hl = hlLayers.includes(layer.id);
    return (
      <div key={layer.id}>
        <LRow layer={layer} dim={dim} primary={pri} hl={hl} hlColor={selObj?.color} hlName={selObj?.name} />
        {i < arr.length - 1 && <VArr c1={layer.color} c2={arr[i + 1].color} />}
      </div>
    );
  };

  return (
    <div style={{
      background: "#07080f", minHeight: "100vh",
      fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace",
      color: "#c8ccd4", padding: "20px 14px", overflow: "auto",
    }}>
      {/* Header */}
      <div style={{ maxWidth: 1120, margin: "0 auto 12px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap", marginBottom: 3 }}>
          <span style={{ fontSize: 9, letterSpacing: 5, color: "#475569" }}>战忽局</span>
          <span style={{ fontSize: 20, fontWeight: 700, color: "#e2e8f0" }}>GeoPulse v7.4</span>
          <span style={{ fontSize: 8, color: "#334155", border: "1px solid #1e293b", borderRadius: 3, padding: "1px 6px" }}>Terminal</span>
        </div>
        <div style={{ fontSize: 9.5, color: "#475569", lineHeight: 1.6 }}>
          <span style={{ color: "#94a3b8" }}>母句:</span> 事件流 → 状态分支概率 → 资产表达
          <span style={{ color: "#1e293b" }}> │ </span>
          <span style={{ color: "#818cf8" }}>Pipeline</span> 做什么 ×{" "}
          <span style={{ color: "#c084fc" }}>Memory</span> 关注什么 ×{" "}
          <span style={{ color: "#f59e0b" }}>Registry</span> 怎么想{" "}
          <span style={{ color: "#1e293b" }}> │ </span>
          <span style={{ color: "#ef4444" }}>+ Constitution 防篡位</span>
        </div>
      </div>

      {/* Axis labels */}
      <div style={{ maxWidth: 1120, margin: "0 auto 4px", display: "grid", gridTemplateColumns: "152px 1fr 340px", gap: 12 }}>
        {[
          { l: "Memory", c: "#c084fc" }, { l: "Pipeline", c: "#818cf8" }, { l: "Model Registry", c: "#f59e0b" },
        ].map((a, i) => (
          <div key={i} style={{ fontSize: 7.5, letterSpacing: 2, color: a.c, textTransform: "uppercase", textAlign: "center", padding: "2px 0", borderBottom: `1px solid ${a.c}1a` }}>{a.l}</div>
        ))}
      </div>

      {/* 3 columns */}
      <div style={{ maxWidth: 1120, margin: "0 auto", display: "grid", gridTemplateColumns: "152px 1fr 340px", gap: 12, alignItems: "start" }}>

        {/* ===== MEMORY ===== */}
        <div style={{ background: "#0c0e18", border: "1px solid #1e293b", borderRadius: 8, padding: "10px 8px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#c084fc", marginBottom: 1 }}>SHS</div>
          <div style={{ fontSize: 7, color: "#64748b", marginBottom: 7 }}>Standing Hypothesis Set</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, marginBottom: 7 }}>
            {["分支名称", "触发信号", "失效信号", "观测对象", "所属期限", "资产表达"].map((f, i) => (
              <div key={i} style={{ fontSize: 7, color: "#94a3b8", padding: "2px 5px", background: "#13151f", borderRadius: 2, borderLeft: "2px solid #7c3aed33" }}>{f}</div>
            ))}
          </div>
          <div style={{ fontSize: 7, color: "#7c3aed", lineHeight: 1.7, marginBottom: 5 }}>
            → L1 注意力先验<br />→ L2a 候选分支<br />→ L4/L5 失效条件
          </div>
          <div style={{ padding: "3px 5px", background: "#ef44440a", border: "1px dashed #ef444418", borderRadius: 3, fontSize: 6.5, color: "#94a3b8", lineHeight: 1.4 }}>
            <span style={{ color: "#ef4444", fontWeight: 600 }}>学习:</span> b/c 重复失效→回写
          </div>
        </div>

        {/* ===== PIPELINE ===== */}
        <div>
          {/* Regime compact */}
          <div style={{ background: "#0c0e18", border: `1px solid ${isB ? "#f59e0b15" : "#1e293b"}`, borderRadius: 6, padding: "5px 8px", marginBottom: 5, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontSize: 7.5, letterSpacing: 1, color: "#64748b" }}>REGIME</span>
              {["A", "B"].map(r => (
                <button key={r} onClick={() => setRegime(r)} style={{
                  background: regime === r ? (r === "A" ? "#3b82f610" : "#f59e0b10") : "transparent",
                  border: `1px solid ${regime === r ? (r === "A" ? "#3b82f6" : "#f59e0b") : "#1e293b"}`,
                  color: regime === r ? (r === "A" ? "#60a5fa" : "#fbbf24") : "#475569",
                  borderRadius: 3, padding: "1px 8px", fontSize: 8, fontWeight: 600,
                  cursor: "pointer", fontFamily: "inherit", transition: "all 0.3s",
                }}>{r === "A" ? "Structural" : "Strategic"}</button>
              ))}
            </div>
            <span style={{ fontSize: 6.5, color: "#334155" }}>demo · 生产环境自动判定</span>
          </div>

          {/* Pre */}
          {pre.map((l, i) => rL(l, i, pre))}
          <VArr c1="#c084fc" c2="#3b82f6" />

          {/* Engine: side-by-side */}
          <div style={{
            border: `1px solid ${isB ? "#f59e0b12" : "#3b82f612"}`,
            borderRadius: 7, padding: "8px 6px 6px", position: "relative", transition: "border-color 0.3s",
          }}>
            <span style={{ fontSize: 6.5, letterSpacing: 1.5, color: "#475569", position: "absolute", top: -6, left: 8, background: "#07080f", padding: "0 3px" }}>DUAL-CORE</span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {eng.map(layer => {
                const dim = (layer.regime === "A" && isB) || (layer.regime === "B" && !isB);
                const pri = (layer.regime === "A" && !isB) || (layer.regime === "B" && isB);
                const hl = hlLayers.includes(layer.id);
                return (
                  <div key={layer.id} style={{
                    background: pri ? `${layer.color}06` : "transparent",
                    border: `1px solid ${pri ? `${layer.color}33` : "#13151f"}`,
                    borderRadius: 6, padding: "7px 8px",
                    opacity: dim ? 0.35 : 1, transition: "all 0.4s",
                    borderRight: hl ? `2px solid ${selObj?.color}33` : undefined,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 3 }}>
                      <span style={{ fontSize: 12, fontWeight: 800, color: layer.color }}>{layer.id}</span>
                      {pri && <span style={{ fontSize: 6, color: layer.color, letterSpacing: 0.8 }}>主引擎</span>}
                      {dim && <span style={{ fontSize: 6, color: "#334155", letterSpacing: 0.8 }}>服务</span>}
                    </div>
                    <div style={{ fontSize: 9, fontWeight: 700, color: "#e2e8f0", marginBottom: 1 }}>{layer.name}</div>
                    <div style={{ fontSize: 7, color: "#475569", marginBottom: 3 }}>{layer.en}</div>
                    <div style={{ fontSize: 7, color: "#64748b", lineHeight: 1.4 }}>{layer.task}</div>
                    {hl && <div style={{ marginTop: 3, fontSize: 6.5, color: selObj?.color, fontWeight: 600 }}>← {selObj?.name}</div>}
                  </div>
                );
              })}
            </div>
            {/* Hybrid bridge */}
            <div style={{
              marginTop: 5, padding: "3px 6px", background: "#ef44440a",
              border: "1px dashed #ef444418", borderRadius: 3,
              fontSize: 7, color: "#94a3b8",
            }}>
              <span style={{ color: "#ef4444", fontWeight: 600 }}>H</span> Hybrid: L3基线 → L3.5修正 → downstream reachable subgraph recomp (one-pass)
            </div>
          </div>

          <VArr c1="#f59e0b" c2="#fbbf24" />
          {post.map((l, i) => rL(l, i, post))}

          {/* Backflow */}
          <div style={{ marginTop: 5, padding: "3px 6px", background: "#0c0e18", borderRadius: 4, border: "1px solid #1e293b", display: "flex", gap: 5, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: 7, color: "#64748b", letterSpacing: 0.8 }}>BACKFLOW</span>
            {[
              { l: "a", t: "Trade→L4/5", c: "#10b981" },
              { l: "b", t: "Scenario→L2", c: "#f59e0b" },
              { l: "c", t: "Regime→重评估", c: "#ef4444" },
            ].map(f => (
              <span key={f.l} style={{ fontSize: 7, color: f.c, padding: "1px 4px", background: `${f.c}0a`, borderRadius: 2 }}>{f.l}. {f.t}</span>
            ))}
          </div>
        </div>

        {/* ===== REGISTRY ===== */}
        <div>
          {/* Constitution */}
          <div style={{
            background: "#0c0e18", borderRadius: 7,
            border: showConstitution ? "1px solid #ef444433" : "1px solid #1e293b",
            padding: "8px 10px", marginBottom: 8, transition: "border-color 0.3s",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: showConstitution ? 6 : 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: "#ef4444" }}>Registry 宪法</span>
                <span style={{ fontSize: 7, color: "#475569" }}>Constitution</span>
              </div>
              <button onClick={() => setShowConstitution(v => !v)} style={{
                background: "transparent", border: "none", fontFamily: "inherit",
                color: "#475569", fontSize: 8, cursor: "pointer",
              }}>{showConstitution ? "▾" : "▸"}</button>
            </div>

            {showConstitution && (
              <div style={{ fontSize: 7.5, lineHeight: 1.7 }}>
                {/* Mother rule */}
                <div style={{
                  padding: "5px 7px", background: "#ef44440a", borderRadius: 4,
                  border: "1px solid #ef444418", marginBottom: 6,
                  color: "#e2e8f0", fontWeight: 600, fontSize: 8,
                }}>
                  母规则: 模型不生成判断，模型只生成视角。判断由 Pipeline 生成。
                </div>

                {/* Corollaries */}
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ padding: "4px 7px", background: "#13151f", borderRadius: 3, borderLeft: "2px solid #f59e0b44" }}>
                    <div style={{ color: "#f59e0b", fontWeight: 600, fontSize: 7.5, marginBottom: 1 }}>推论一: 调用权归 Pipeline</div>
                    <div style={{ color: "#64748b" }}>模型不自行出场。Pipeline 在处理节点时向 Registry 发请求，由 callable_when 条件判定是否加载。主语始终是 Pipeline。</div>
                  </div>
                  <div style={{ padding: "4px 7px", background: "#13151f", borderRadius: 3, borderLeft: "2px solid #a78bfa44" }}>
                    <div style={{ color: "#a78bfa", fontWeight: 600, fontSize: 7.5, marginBottom: 1 }}>推论二: 冲突不解决，标记为信号</div>
                    <div style={{ color: "#64748b" }}>同层多模型输出不同结论时，不投票、不取均值。标记 <span style={{ color: "#a78bfa" }}>divergence flag</span>，上报 L2a 生成新分支。分歧 = 深挖信号。</div>
                  </div>
                  <div style={{ padding: "4px 7px", background: "#13151f", borderRadius: 3, borderLeft: "2px solid #10b98144" }}>
                    <div style={{ color: "#10b981", fontWeight: 600, fontSize: 7.5, marginBottom: 1 }}>推论三: 信用评分分两维</div>
                    <div style={{ color: "#64748b" }}>
                      <span style={{ color: "#3b82f6" }}>P 类 (Productive)</span> 产出判断 → 评 predictive utility<br />
                      <span style={{ color: "#a78bfa" }}>D 类 (Disciplinary)</span> 质疑判断 → 评 risk coverage<br />
                      D 类不因"风险没发生"被降级。
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Category filter */}
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap", marginBottom: 5 }}>
            <button onClick={() => { setFilterCat(null); setSelModel(null); }} style={{
              background: !filterCat ? "#ffffff08" : "transparent", border: `1px solid ${!filterCat ? "#475569" : "#1e293b"}`,
              color: !filterCat ? "#94a3b8" : "#334155", borderRadius: 3, padding: "1px 6px", fontSize: 7, cursor: "pointer", fontFamily: "inherit",
            }}>全部</button>
            {CATEGORIES.map(cat => (
              <button key={cat} onClick={() => { setFilterCat(filterCat === cat ? null : cat); setSelModel(null); }} style={{
                background: filterCat === cat ? `${CC[cat]}10` : "transparent",
                border: `1px solid ${filterCat === cat ? CC[cat] : "#1e293b"}`,
                color: filterCat === cat ? CC[cat] : "#334155",
                borderRadius: 3, padding: "1px 6px", fontSize: 7, cursor: "pointer", fontFamily: "inherit",
              }}>{cat}</button>
            ))}
          </div>

          {/* Model Card v2 list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {filtered.map(m => {
              const isSel = selModel === m.id;
              return (
                <div key={m.id} onClick={() => setSelModel(isSel ? null : m.id)} style={{
                  background: isSel ? `${m.color}0c` : "#0c0e18",
                  border: `1px solid ${isSel ? `${m.color}33` : "#1e293b"}`,
                  borderRadius: 5, padding: "6px 8px", cursor: "pointer", transition: "all 0.2s",
                }}>
                  {/* Header row */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                    <span style={{ fontSize: 9, fontWeight: 700, color: "#e2e8f0" }}>{m.name}</span>
                    <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
                      <span style={{
                        fontSize: 6.5, fontWeight: 700,
                        color: m.role === "P" ? "#3b82f6" : "#a78bfa",
                        padding: "0px 4px",
                        background: m.role === "P" ? "#3b82f612" : "#a78bfa12",
                        borderRadius: 2,
                      }}>{m.role}</span>
                      <span style={{ fontSize: 6.5, color: "#475569", padding: "0px 3px", background: "#13151f", borderRadius: 2 }}>
                        {m.cost}
                      </span>
                    </div>
                  </div>

                  {/* Layer + category tags */}
                  <div style={{ display: "flex", gap: 2, flexWrap: "wrap", alignItems: "center" }}>
                    {m.layers.map(lid => {
                      const lc = LAYERS.find(l => l.id === lid)?.color || "#475569";
                      return <span key={lid} style={{ fontSize: 6.5, color: lc, padding: "0px 3px", background: `${lc}12`, borderRadius: 2, fontWeight: 600 }}>{lid}</span>;
                    })}
                    <span style={{ fontSize: 6.5, color: CC[m.cat], marginLeft: 2 }}>{m.cat}</span>
                  </div>

                  {/* Expanded: Model Card v2 */}
                  {isSel && (
                    <div style={{ fontSize: 7, color: "#64748b", lineHeight: 1.6, borderTop: "1px solid #1e293b", paddingTop: 4, marginTop: 4 }}>
                      <div><span style={{ color: "#94a3b8" }}>callable_when:</span> {m.callable}</div>
                      <div><span style={{ color: "#94a3b8" }}>输入:</span> {m.input}</div>
                      <div><span style={{ color: "#94a3b8" }}>输出:</span> {m.output}</div>
                      <div><span style={{ color: "#94a3b8" }}>scope:</span> {m.scope}</div>
                      <div style={{ marginTop: 2, display: "flex", gap: 6 }}>
                        <span>
                          <span style={{ color: "#94a3b8" }}>role:</span>{" "}
                          <span style={{ color: m.role === "P" ? "#3b82f6" : "#a78bfa", fontWeight: 600 }}>
                            {m.role === "P" ? "Productive" : "Disciplinary"}
                          </span>
                        </span>
                        <span>
                          <span style={{ color: "#94a3b8" }}>cost:</span>{" "}
                          <span style={{ color: m.cost === "heavy" ? "#ef4444" : m.cost === "medium" ? "#fbbf24" : "#10b981" }}>
                            {m.cost}
                          </span>
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Model Card v2 schema */}
          <div style={{
            marginTop: 8, padding: "5px 7px", background: "#0f111a",
            borderRadius: 4, border: "1px solid #1e293b",
          }}>
            <div style={{ fontSize: 7.5, color: "#94a3b8", fontWeight: 600, marginBottom: 2 }}>Model Card v2 Schema</div>
            <div style={{ fontSize: 7, color: "#475569", lineHeight: 1.6 }}>
              名称 · 类别 · 适用层位 · 输入接口 · 输出接口<br />
              <span style={{ color: "#f59e0b" }}>callable_when</span> (主语=Pipeline, 非模型自触发)<br />
              <span style={{ color: "#64748b" }}>scope</span> (适用域 + 明确"不适用"边界)<br />
              <span style={{ color: "#3b82f6" }}>role: P</span> | <span style={{ color: "#a78bfa" }}>D</span> · cost: light|med|heavy<br />
              <span style={{ color: "#10b981" }}>credit</span>: P→predictive util / D→risk coverage
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ maxWidth: 1120, margin: "12px auto 0", display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
        {[
          { axis: "Pipeline", desc: "做什么 — 固定", c: "#818cf8", p: "主语·分流·回流" },
          { axis: "Memory", desc: "关注什么 — 可学习", c: "#c084fc", p: "先验·注意力·失效" },
          { axis: "Registry", desc: "怎么想 — 可插拔", c: "#f59e0b", p: "Card v2·跨层·竞争" },
          { axis: "Constitution", desc: "防篡位 — 刚性", c: "#ef4444", p: "调用权归Pipeline·分歧=信号·P/D双评" },
        ].map((a, i) => (
          <div key={i} style={{ padding: "5px 8px", background: "#0c0e18", borderRadius: 5, border: "1px solid #1e293b" }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: a.c, marginBottom: 1 }}>{a.axis}</div>
            <div style={{ fontSize: 7.5, color: "#94a3b8", marginBottom: 1 }}>{a.desc}</div>
            <div style={{ fontSize: 7, color: "#475569" }}>{a.p}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
