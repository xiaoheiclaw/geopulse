"""Scenario-level time phases for the conflict timeline.

All prediction/state nodes share the same global phase grid.
Each node distributes its probability across these phases.
"""

# Global phases for the US-Iran conflict scenario
CONFLICT_PHASES = [
    {
        "id": "w1_2",
        "label": "冲击期",
        "weeks": "W1-2",
        "start_date": "2026-02-28",
        "end_date": "2026-03-14",
    },
    {
        "id": "w3_5",
        "label": "Trump时间表窗口",
        "weeks": "W3-5",
        "start_date": "2026-03-14",
        "end_date": "2026-04-04",
    },
    {
        "id": "w6_10",
        "label": "第一消耗期",
        "weeks": "W6-10",
        "start_date": "2026-04-04",
        "end_date": "2026-05-09",
    },
    {
        "id": "w11_16",
        "label": "疲劳/升级分叉",
        "weeks": "W11-16",
        "start_date": "2026-05-09",
        "end_date": "2026-06-20",
    },
    {
        "id": "w17_24",
        "label": "深度消耗",
        "weeks": "W17-24",
        "start_date": "2026-06-20",
        "end_date": "2026-08-15",
    },
    {
        "id": "w25_plus",
        "label": "长尾/结构性僵局",
        "weeks": "W25+",
        "start_date": "2026-08-15",
        "end_date": "",
    },
]
