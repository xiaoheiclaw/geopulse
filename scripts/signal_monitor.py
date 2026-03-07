#!/usr/bin/env python3
"""
GeoPulse Leading Signal Monitor
Checks leading indicators and flags alerts.
Run via cron every 4-6 hours.
"""

import json
import urllib.request
import urllib.error
import datetime
import os
import re
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ALERTS_FILE = os.path.join(DATA_DIR, "signal_alerts.json")

def load_alerts():
    if os.path.exists(ALERTS_FILE):
        return json.load(open(ALERTS_FILE))
    return {"alerts": [], "last_check": None, "baselines": {}}

def save_alerts(data):
    data["last_check"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(ALERTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "GeoPulse/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠ fetch error: {url} — {e}")
        return None

def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "GeoPulse/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠ fetch error: {url} — {e}")
        return None

# ═══════════════════════════════════════════
# SIGNAL CHECKERS
# ═══════════════════════════════════════════

def check_oil_price(state):
    """T01/T02: Brent price level + weekly change"""
    # Yahoo Finance API for Brent
    url = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?interval=1d&range=5d"
    data = fetch_json(url)
    if not data:
        return []
    alerts = []
    try:
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            latest = closes[-1]
            prev = closes[0]
            weekly_chg = (latest - prev) / prev * 100
            state["baselines"]["brent_latest"] = latest
            state["baselines"]["brent_weekly_chg"] = weekly_chg
            
            if latest > 95:
                alerts.append({
                    "signal_id": "T01",
                    "level": "P0",
                    "message": f"Brent ${latest:.2f} — 距$100仅${100-latest:.1f}",
                    "action": "检查call skew和backwardation",
                })
            if weekly_chg > 15:
                alerts.append({
                    "signal_id": "T01",
                    "level": "P1",
                    "message": f"Brent周涨{weekly_chg:.1f}% — 异常波动",
                    "action": "评估是否需要减仓获利",
                })
    except (KeyError, IndexError):
        pass
    return alerts

def check_vix(state):
    """T04/T05: VIX level + term structure"""
    alerts = []
    # VIX
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if closes:
                vix = closes[-1]
                state["baselines"]["vix"] = vix
                if vix > 35:
                    alerts.append({
                        "signal_id": "T04",
                        "level": "P1",
                        "message": f"VIX {vix:.1f} > 35 — 恐慌区间",
                        "action": "检查VIX期限结构是否倒挂",
                    })
                if vix > 45:
                    alerts.append({
                        "signal_id": "T04",
                        "level": "P0",
                        "message": f"VIX {vix:.1f} > 45 — 极端恐慌",
                        "action": "考虑VIX多头获利了结",
                    })
        except (KeyError, IndexError):
            pass
    
    # VIX3M for term structure
    data3m = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX3M?interval=1d&range=2d")
    if data3m:
        try:
            closes3m = [c for c in data3m["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if closes3m and "vix" in state.get("baselines", {}):
                vix3m = closes3m[-1]
                vix = state["baselines"]["vix"]
                state["baselines"]["vix3m"] = vix3m
                if vix > vix3m:
                    alerts.append({
                        "signal_id": "T05",
                        "level": "P1",
                        "message": f"VIX期限倒挂: VIX {vix:.1f} > VIX3M {vix3m:.1f}",
                        "action": "近期尾部风险定价升高，加仓尾部对冲",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

def check_em_fx(state):
    """T11/T12: EM FX stress"""
    alerts = []
    pairs = {"TRY": "USDTRY=X", "INR": "USDINR=X", "CNY": "USDCNH=X"}
    for name, ticker in pairs.items():
        data = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d")
        if data:
            try:
                closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
                if len(closes) >= 2:
                    latest = closes[-1]
                    prev = closes[-2]
                    daily_chg = (latest - prev) / prev * 100
                    state["baselines"][f"{name}_rate"] = latest
                    state["baselines"][f"{name}_daily_chg"] = daily_chg
                    
                    thresholds = {"TRY": 3.0, "INR": 1.5, "CNY": 0.5}
                    if daily_chg > thresholds.get(name, 2.0):
                        alerts.append({
                            "signal_id": "T11",
                            "level": "P1",
                            "message": f"{name} 单日贬值{daily_chg:.2f}% (>{thresholds[name]}%阈值)",
                            "action": f"加仓{name} short",
                        })
            except (KeyError, IndexError):
                pass
    
    # CNY specific: check if > 7.50
    cny = state.get("baselines", {}).get("CNY_rate", 0)
    if cny > 7.45:
        alerts.append({
            "signal_id": "T12",
            "level": "P1",
            "message": f"USD/CNH {cny:.4f} 接近7.50关口",
            "action": "关注PBOC中间价信号",
        })
    return alerts

def check_ccj_volume(state):
    """T08: Uranium/CCJ abnormal volume"""
    alerts = []
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/CCJ?interval=1d&range=20d")
    if data:
        try:
            vols = [v for v in data["chart"]["result"][0]["indicators"]["quote"][0]["volume"] if v]
            if len(vols) >= 5:
                avg_vol = sum(vols[:-1]) / len(vols[:-1])
                latest_vol = vols[-1]
                ratio = latest_vol / avg_vol if avg_vol > 0 else 0
                state["baselines"]["ccj_vol_ratio"] = ratio
                if ratio > 3:
                    alerts.append({
                        "signal_id": "T08",
                        "level": "P1",
                        "message": f"CCJ成交量{ratio:.1f}x均量 — 核信号聪明钱?",
                        "action": "加速建仓CCJ/SRUUF",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

def check_gold_yields(state):
    """Gold vs yields divergence (stagflation signal)"""
    alerts = []
    # Gold
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if closes:
                state["baselines"]["gold"] = closes[-1]
        except (KeyError, IndexError):
            pass
    # 10Y yield
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?interval=1d&range=5d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                latest = closes[-1]
                prev = closes[0]
                state["baselines"]["tnx"] = latest
                if latest > 4.5:
                    alerts.append({
                        "signal_id": "STAGFLATION",
                        "level": "P1",
                        "message": f"10Y yield {latest:.2f}% > 4.5% — 滞胀定价区间",
                        "action": "确认treasury_stagflation节点概率",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

def check_sp500(state):
    """S&P 500 drawdown from recent high"""
    alerts = []
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=30d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 5:
                peak = max(closes)
                latest = closes[-1]
                drawdown = (latest - peak) / peak * 100
                state["baselines"]["sp500"] = latest
                state["baselines"]["sp500_drawdown"] = drawdown
                if drawdown < -5:
                    alerts.append({
                        "signal_id": "EQUITY",
                        "level": "P0",
                        "message": f"S&P 500 从高点回撤{drawdown:.1f}% — 触及-5%阈值",
                        "action": "equity_correction节点可能需要上调",
                    })
                elif drawdown < -3:
                    alerts.append({
                        "signal_id": "EQUITY",
                        "level": "P1",
                        "message": f"S&P 500 从高点回撤{drawdown:.1f}%",
                        "action": "接近-5%阈值，关注信用市场确认",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def run_all_checks():
    state = load_alerts()
    all_alerts = []
    
    checkers = [
        ("Oil/Brent", check_oil_price),
        ("VIX/Term Structure", check_vix),
        ("EM FX", check_em_fx),
        ("CCJ Volume", check_ccj_volume),
        ("Gold/Yields", check_gold_yields),
        ("S&P 500", check_sp500),
    ]
    
    print(f"GeoPulse Signal Monitor — {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print("=" * 60)
    
    for name, checker in checkers:
        print(f"\n🔍 {name}...")
        try:
            alerts = checker(state)
            all_alerts.extend(alerts)
            if not alerts:
                print("  ✅ No alerts")
            for a in alerts:
                print(f"  {'🔴' if a['level']=='P0' else '🟡'} [{a['signal_id']}] {a['message']}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Save results
    state["alerts"] = all_alerts
    state["alert_count"] = len(all_alerts)
    state["p0_count"] = sum(1 for a in all_alerts if a["level"] == "P0")
    save_alerts(state)
    
    print(f"\n{'=' * 60}")
    print(f"Total: {len(all_alerts)} alerts ({state['p0_count']} P0)")
    
    # Print baselines
    print(f"\n📊 Baselines:")
    for k, v in sorted(state.get("baselines", {}).items()):
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}" if v < 10 else f"  {k}: {v:.2f}")
    
    return state

if __name__ == "__main__":
    state = run_all_checks()
    
    # Output summary for cron consumption
    if state["p0_count"] > 0:
        print(f"\n🚨 {state['p0_count']} P0 ALERTS — PUSH REQUIRED")
        sys.exit(1)  # Non-zero = has P0 alerts
    sys.exit(0)
