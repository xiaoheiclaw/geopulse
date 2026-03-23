#!/usr/bin/env python3
"""Update focal_tracker.json safely — avoids Edit tool failures on large files.

Usage from pipeline:
    python scripts/update_focal_tracker.py --q1 "3+" --q1-note "Day 24, coordinated attacks"
    python scripts/update_focal_tracker.py --q2 "<2" --q2-note "near zero transit"
    python scripts/update_focal_tracker.py --q3 "0" --q3-note "zero physical drawdown"
    python scripts/update_focal_tracker.py --fp1 "not_detected" --fp1-note "no cost action"
    python scripts/update_focal_tracker.py --fp2 "watching" --fp2-note "SPR vs Kharg contradiction"
    python scripts/update_focal_tracker.py --fp3 "not_detected"
    python scripts/update_focal_tracker.py --fp4 "approaching" --fp4-note "gas $4, 53% oppose"
    python scripts/update_focal_tracker.py --compact  # trim history to last 14 days
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRACKER_PATH = DATA_DIR / "focal_tracker.json"
DB_PATH = DATA_DIR / "geopulse.db"


def _ensure_table():
    """Create focal_history table if needed."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS focal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                layer TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                note TEXT,
                source TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_focal_ts ON focal_history(timestamp)
        """)


def _load_tracker() -> dict:
    if TRACKER_PATH.exists():
        with open(TRACKER_PATH) as f:
            return json.load(f)
    return {}


def _save_tracker(data: dict):
    """Save tracker with compact history (last 14 entries per observable)."""
    # Trim physical history to last 14 entries
    phys = data.get("physical_observables", {})
    for key in ["q1_attack_frequency", "q2_strait_transit", "q3_spr_release_rate"]:
        obs = phys.get(key, {})
        if "history" in obs and len(obs["history"]) > 14:
            obs["history"] = obs["history"][-14:]

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(TRACKER_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    size = TRACKER_PATH.stat().st_size
    print(f"focal_tracker.json updated ({size} bytes)")


def _log_to_db(layer: str, key: str, value: str, note: str = "", source: str = "pipeline"):
    """Write history entry to SQLite instead of bloating JSON."""
    _ensure_table()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO focal_history (timestamp, layer, key, value, note, source) VALUES (?, ?, ?, ?, ?, ?)",
            (now, layer, key, value, note, source)
        )


def update_physical(tracker: dict, q1=None, q1_note=None, q2=None, q2_note=None, q3=None, q3_note=None):
    phys = tracker.setdefault("physical_observables", {})
    now = datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")

    if q1 is not None:
        obs = phys.setdefault("q1_attack_frequency", {})
        history = obs.setdefault("history", [])
        entry = {"date": date, "est": q1, "note": q1_note or "", "source": "pipeline"}
        history.append(entry)
        _log_to_db("physical", "q1_attack_frequency", q1, q1_note or "")
        print(f"  Q1 updated: {q1}")

    if q2 is not None:
        obs = phys.setdefault("q2_strait_transit", {})
        history = obs.setdefault("history", [])
        entry = {"date": date, "est": q2, "note": q2_note or "", "source": "pipeline"}
        history.append(entry)
        _log_to_db("physical", "q2_strait_transit", q2, q2_note or "")
        print(f"  Q2 updated: {q2}")

    if q3 is not None:
        obs = phys.setdefault("q3_spr_release_rate", {})
        history = obs.setdefault("history", [])
        entry = {"date": date, "est": q3, "note": q3_note or "", "source": "pipeline"}
        history.append(entry)
        _log_to_db("physical", "q3_spr_release_rate", q3, q3_note or "")
        print(f"  Q3 updated: {q3}")


def update_focal(tracker: dict, fp1=None, fp1_note=None, fp2=None, fp2_note=None,
                 fp3=None, fp3_note=None, fp4=None, fp4_note=None):
    signals = tracker.setdefault("focal_signals", {})

    for key, status, note in [
        ("fp1_china_action", fp1, fp1_note),
        ("fp2_us_signal_inconsistency", fp2, fp2_note),
        ("fp3_face_saving_framework", fp3, fp3_note),
        ("fp4_cost_threshold", fp4, fp4_note),
    ]:
        if status is not None:
            sig = signals.setdefault(key, {})
            sig["status"] = status
            sig["last_check"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if note:
                sig["findings"] = note
            _log_to_db("focal", key, status, note or "")
            print(f"  {key}: {status}")


def compact(tracker: dict):
    """Aggressively compact the tracker file."""
    phys = tracker.get("physical_observables", {})
    for key in ["q1_attack_frequency", "q2_strait_transit", "q3_spr_release_rate"]:
        obs = phys.get(key, {})
        if "history" in obs:
            obs["history"] = obs["history"][-7:]  # keep only last 7

    # Remove verbose fields that bloat
    for key in list(tracker.keys()):
        if key.startswith("_") or key == "design_note":
            del tracker[key]

    print("  Compacted tracker")


def main():
    parser = argparse.ArgumentParser(description="Update focal_tracker.json safely")
    parser.add_argument("--q1", help="Q1 attack frequency estimate")
    parser.add_argument("--q1-note", help="Q1 note")
    parser.add_argument("--q2", help="Q2 strait transit estimate")
    parser.add_argument("--q2-note", help="Q2 note")
    parser.add_argument("--q3", help="Q3 SPR release rate estimate")
    parser.add_argument("--q3-note", help="Q3 note")
    parser.add_argument("--fp1", help="fp1 China action status")
    parser.add_argument("--fp1-note", help="fp1 note")
    parser.add_argument("--fp2", help="fp2 US signal inconsistency status")
    parser.add_argument("--fp2-note", help="fp2 note")
    parser.add_argument("--fp3", help="fp3 face-saving framework status")
    parser.add_argument("--fp3-note", help="fp3 note")
    parser.add_argument("--fp4", help="fp4 cost threshold status")
    parser.add_argument("--fp4-note", help="fp4 note")
    parser.add_argument("--compact", action="store_true", help="Compact tracker aggressively")

    args = parser.parse_args()
    tracker = _load_tracker()

    if args.compact:
        compact(tracker)

    update_physical(tracker, args.q1, args.q1_note, args.q2, args.q2_note, args.q3, args.q3_note)
    update_focal(tracker, args.fp1, args.fp1_note, args.fp2, args.fp2_note,
                 args.fp3, args.fp3_note, args.fp4, args.fp4_note)

    _save_tracker(tracker)


if __name__ == "__main__":
    main()
