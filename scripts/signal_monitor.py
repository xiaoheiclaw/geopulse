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
        ("Oil Implied Vol (OVX)", check_ovx),
        ("Brent Curve", check_brent_contango),
        ("VIX/Term Structure", check_vix),
        ("SKEW Index", check_skew_index),
        ("Credit Stress (HYG/LQD)", check_hy_spread_proxy),
        ("EM FX", check_em_fx),
        ("DXY", check_dxy),
        ("CCJ Volume", check_ccj_volume),
        ("Gold/Yields", check_gold_yields),
        ("S&P 500", check_sp500),
        ("News Flags", check_news_signals),
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




# ═══════════════════════════════════════════
# ADDITIONAL SIGNAL CHECKERS (Batch 2)
# ═══════════════════════════════════════════

def check_skew_index(state):
    """T05 supplement: CBOE SKEW index"""
    alerts = []
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5ESKEW?interval=1d&range=5d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if closes:
                skew = closes[-1]
                state["baselines"]["skew"] = skew
                if skew > 150:
                    alerts.append({
                        "signal_id": "T05",
                        "level": "P1",
                        "message": f"SKEW {skew:.0f} > 150 — 尾部风险定价极端",
                        "action": "叠加VIX倒挂 = 强烈尾部对冲信号",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

def check_brent_contango(state):
    """T01 supplement: Brent front-month vs 3-month spread (backwardation)"""
    alerts = []
    # Front month
    d1 = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?interval=1d&range=2d")
    # Use CL (WTI) 3-month as proxy since Brent 3M not easily available
    # Check WTI front vs deferred
    d2 = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1d&range=2d")
    d3 = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/CLK26.NYM?interval=1d&range=2d")  # May 2026
    if d1 and d2:
        try:
            brent = [c for c in d1["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c][-1]
            wti_front = [c for c in d2["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c][-1]
            state["baselines"]["brent_front"] = brent
            state["baselines"]["wti_front"] = wti_front
            # Brent-WTI spread
            spread = brent - wti_front
            state["baselines"]["brent_wti_spread"] = spread
        except (KeyError, IndexError):
            pass
    return alerts

def check_hy_spread_proxy(state):
    """T04 proxy: HYG vs LQD ratio as credit stress proxy"""
    alerts = []
    hyg = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/HYG?interval=1d&range=10d")
    lqd = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/LQD?interval=1d&range=10d")
    if hyg and lqd:
        try:
            hyg_c = [c for c in hyg["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            lqd_c = [c for c in lqd["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(hyg_c) >= 5 and len(lqd_c) >= 5:
                # HYG/LQD ratio — falling = credit stress rising
                ratio_now = hyg_c[-1] / lqd_c[-1]
                ratio_5d = hyg_c[0] / lqd_c[0]
                chg = (ratio_now - ratio_5d) / ratio_5d * 100
                state["baselines"]["hyg_lqd_ratio"] = ratio_now
                state["baselines"]["hyg_lqd_5d_chg"] = chg
                if chg < -1.5:
                    alerts.append({
                        "signal_id": "T04",
                        "level": "P1",
                        "message": f"HYG/LQD比率5日下跌{chg:.2f}% — 信用压力上升",
                        "action": "信用市场领先股市，加仓VIX/减risk-on",
                    })
                if chg < -3.0:
                    alerts.append({
                        "signal_id": "T04",
                        "level": "P0",
                        "message": f"HYG/LQD比率5日暴跌{chg:.2f}% — 信用市场恐慌",
                        "action": "立即加仓尾部对冲，考虑减持全部risk-on",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

def check_ovx(state):
    """T01/T10 supplement: Oil VIX (OVX) for implied vol"""
    alerts = []
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/%5EOVX?interval=1d&range=10d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                ovx = closes[-1]
                ovx_prev = closes[-2]
                ovx_5d_ago = closes[0] if len(closes) >= 5 else closes[0]
                daily_chg = ovx - ovx_prev
                state["baselines"]["ovx"] = ovx
                state["baselines"]["ovx_daily_chg"] = daily_chg
                # T10: implied vol突降 but spot didn't drop = someone knows something
                brent = state.get("baselines", {}).get("brent_latest", 0)
                brent_chg = state.get("baselines", {}).get("brent_weekly_chg", 0)
                if daily_chg < -5 and brent_chg >= 0:
                    alerts.append({
                        "signal_id": "T10",
                        "level": "P0",
                        "message": f"OVX单日跌{daily_chg:.1f}vol但Brent未跌 — 风险定价异常下降",
                        "action": "密切关注外交动态，可能有停火后渠道信号",
                    })
                if ovx > 60:
                    alerts.append({
                        "signal_id": "T01",
                        "level": "P1",
                        "message": f"OVX {ovx:.1f} > 60 — 油价波动率极端",
                        "action": "考虑用期权替代期货(买call spread代替裸多)",
                    })
        except (KeyError, IndexError):
            pass
    return alerts

def check_news_signals(state):
    """T03/T06/T07/T09: News-based signals via keyword detection
    Note: Requires web_search which isn't available in pure Python.
    This checker reads from a manually-updated news flags file.
    """
    alerts = []
    news_file = os.path.join(DATA_DIR, "news_flags.json")
    if os.path.exists(news_file):
        flags = json.load(open(news_file))
        for flag in flags.get("active", []):
            alerts.append({
                "signal_id": flag.get("trigger_id", "NEWS"),
                "level": flag.get("level", "P1"),
                "message": flag["message"],
                "action": flag.get("action", "评估影响"),
            })
    return alerts

def check_dxy(state):
    """DXY strength — feeds into EM capital outflow"""
    alerts = []
    data = fetch_json("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=10d")
    if data:
        try:
            closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 5:
                latest = closes[-1]
                wk_ago = closes[0]
                wk_chg = (latest - wk_ago) / wk_ago * 100
                state["baselines"]["dxy"] = latest
                state["baselines"]["dxy_weekly_chg"] = wk_chg
                if wk_chg > 2:
                    alerts.append({
                        "signal_id": "T11",
                        "level": "P1",
                        "message": f"DXY周涨{wk_chg:.1f}%至{latest:.1f} — 美元走强压EM",
                        "action": "EM FX short加仓信号",
                    })
        except (KeyError, IndexError):
            pass
    return alerts


if __name__ == "__main__":
    state = run_all_checks()
    
    # Output summary for cron consumption
    if state["p0_count"] > 0:
        print(f"\n🚨 {state['p0_count']} P0 ALERTS — PUSH REQUIRED")
        sys.exit(1)  # Non-zero = has P0 alerts
    sys.exit(0)