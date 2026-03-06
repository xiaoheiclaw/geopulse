"""Regime detection — three-factor scoring with hysteresis.

Regime A = Structural (mechanical causal propagation dominates)
Regime B = Strategic (game-theoretic resolution dominates)

Three factors:
- SAD: Strategic Actor Density — proportion of S-type nodes in bottlenecks
- PD:  Payoff Dependence — inter-node payoff coupling (DAG edge density proxy)
- NCC: Non-Cooperative Complexity — edge weight on S/H nodes
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from .run_output import (
    BottleneckNode,
    FactorScores,
    Hysteresis,
    NodeType,
    Regime,
    RegimeState,
)

# ── Defaults ──
W_SAD = 0.4
W_PD = 0.3
W_NCC = 0.3
ENTER_THRESHOLD = 0.55  # A → B
EXIT_THRESHOLD = 0.40   # B → A
MIN_HOLD = timedelta(hours=24)


class RegimeDetector:
    """Computes regime from bottleneck node factor scores."""

    def __init__(
        self,
        w_sad: float = W_SAD,
        w_pd: float = W_PD,
        w_ncc: float = W_NCC,
        enter_threshold: float = ENTER_THRESHOLD,
        exit_threshold: float = EXIT_THRESHOLD,
        min_hold: timedelta = MIN_HOLD,
    ):
        self.w_sad = w_sad
        self.w_pd = w_pd
        self.w_ncc = w_ncc
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold
        self.min_hold = min_hold

    def compute_factors(self, bottlenecks: list[BottleneckNode]) -> FactorScores:
        """Aggregate three factors from bottleneck nodes.

        SAD = proportion of S/H type nodes (strategic actor density)
        PD  = average path_importance (proxy for payoff dependence)
        NCC = weighted average of factor_scores.NCC from S/H nodes
        """
        if not bottlenecks:
            return FactorScores(SAD=0.0, PD=0.0, NCC=0.0)

        n = len(bottlenecks)

        # SAD: strategic actor density
        strategic_count = sum(
            1 for b in bottlenecks if b.type in (NodeType.S, NodeType.H)
        )
        sad = strategic_count / n

        # PD: payoff dependence (proxy: average path_importance)
        pd = sum(b.path_importance for b in bottlenecks) / n

        # NCC: non-cooperative complexity (from S/H nodes)
        sh_nodes = [b for b in bottlenecks if b.type in (NodeType.S, NodeType.H)]
        if sh_nodes:
            ncc = sum(b.factor_scores.NCC for b in sh_nodes) / len(sh_nodes)
        else:
            ncc = 0.0

        return FactorScores(
            SAD=round(sad, 4),
            PD=round(pd, 4),
            NCC=round(ncc, 4),
        )

    def determine_regime(
        self,
        factors: FactorScores,
        current: RegimeState | None = None,
    ) -> RegimeState:
        """Determine regime with hysteresis to prevent oscillation.

        A→B: joint > enter_threshold AND held > min_hold
        B→A: joint < exit_threshold AND held > min_hold
        """
        joint = (
            self.w_sad * factors.SAD
            + self.w_pd * factors.PD
            + self.w_ncc * factors.NCC
        )
        joint = round(min(1.0, max(0.0, joint)), 4)

        now = datetime.now(timezone.utc)

        if current is None:
            # First run — default to Regime A
            return RegimeState(
                current=Regime.A,
                previous=Regime.A,
                switched=False,
                held_since=now,
                factor_scores=factors,
                joint_score=joint,
                hysteresis=Hysteresis(
                    enter_threshold=self.enter_threshold,
                    exit_threshold=self.exit_threshold,
                    min_hold="PT24H",
                    time_in_current="PT0S",
                ),
            )

        held_duration = now - current.held_since
        held_long_enough = held_duration >= self.min_hold
        new_regime = current.current
        switched = False

        if current.current == Regime.A and joint > self.enter_threshold and held_long_enough:
            new_regime = Regime.B
            switched = True
        elif current.current == Regime.B and joint < self.exit_threshold and held_long_enough:
            new_regime = Regime.A
            switched = True

        held_since = now if switched else current.held_since
        time_in = now - held_since

        # Format duration as ISO 8601
        total_seconds = int(time_in.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        time_str = f"PT{hours}H{minutes}M{secs}S" if hours else f"PT{minutes}M{secs}S"

        return RegimeState(
            current=new_regime,
            previous=current.current,
            switched=switched,
            held_since=held_since,
            factor_scores=factors,
            joint_score=joint,
            hysteresis=Hysteresis(
                enter_threshold=self.enter_threshold,
                exit_threshold=self.exit_threshold,
                min_hold="PT24H",
                time_in_current=time_str,
            ),
        )
