"""Tests for Regime detection — three-factor scoring with hysteresis."""
from datetime import datetime, timedelta, timezone

import pytest

from geopulse.regime import RegimeDetector
from geopulse.run_output import (
    BottleneckNode,
    FactorScores,
    Hysteresis,
    NodeType,
    Regime,
    RegimeState,
)


@pytest.fixture
def detector():
    return RegimeDetector()


def _bn(type: str = "M", path_importance: float = 0.5, ncc: float = 0.3) -> BottleneckNode:
    return BottleneckNode(
        node_id=f"bn_{type}",
        label=f"test_{type}",
        type=NodeType(type),
        path_importance=path_importance,
        factor_scores=FactorScores(SAD=0.5, PD=0.5, NCC=ncc),
    )


def test_compute_factors_empty(detector):
    f = detector.compute_factors([])
    assert f.SAD == 0.0
    assert f.PD == 0.0
    assert f.NCC == 0.0


def test_compute_factors_all_mechanical(detector):
    bottlenecks = [_bn("M"), _bn("M")]
    f = detector.compute_factors(bottlenecks)
    assert f.SAD == 0.0  # No S/H nodes
    assert f.PD == 0.5   # avg path_importance
    assert f.NCC == 0.0  # No S/H nodes for NCC


def test_compute_factors_mixed(detector):
    bottlenecks = [_bn("M"), _bn("S", ncc=0.8), _bn("H", ncc=0.6)]
    f = detector.compute_factors(bottlenecks)
    assert f.SAD == pytest.approx(2 / 3, rel=0.01)  # 2 out of 3 are S/H
    assert f.PD == 0.5  # all default path_importance
    assert f.NCC == pytest.approx(0.7, rel=0.01)  # avg(0.8, 0.6)


def test_determine_regime_first_run(detector):
    factors = FactorScores(SAD=0.0, PD=0.0, NCC=0.0)
    state = detector.determine_regime(factors, current=None)
    assert state.current == Regime.A
    assert state.previous == Regime.A
    assert state.switched is False


def test_determine_regime_stays_in_a(detector):
    """Low joint score stays in Regime A."""
    factors = FactorScores(SAD=0.2, PD=0.1, NCC=0.1)
    now = datetime.now(timezone.utc)
    current = RegimeState(
        current=Regime.A,
        previous=Regime.A,
        switched=False,
        held_since=now - timedelta(hours=48),
        factor_scores=factors,
        joint_score=0.14,
        hysteresis=Hysteresis(
            enter_threshold=0.55, exit_threshold=0.40,
            min_hold="PT24H", time_in_current="PT48H",
        ),
    )
    state = detector.determine_regime(factors, current=current)
    assert state.current == Regime.A
    assert state.switched is False


def test_determine_regime_switch_to_b(detector):
    """High joint score + held long enough → switch to B."""
    factors = FactorScores(SAD=0.8, PD=0.7, NCC=0.6)
    now = datetime.now(timezone.utc)
    current = RegimeState(
        current=Regime.A,
        previous=Regime.A,
        switched=False,
        held_since=now - timedelta(hours=48),
        factor_scores=FactorScores(SAD=0.3, PD=0.3, NCC=0.3),
        joint_score=0.3,
        hysteresis=Hysteresis(
            enter_threshold=0.55, exit_threshold=0.40,
            min_hold="PT24H", time_in_current="PT48H",
        ),
    )
    state = detector.determine_regime(factors, current=current)
    assert state.current == Regime.B
    assert state.switched is True
    assert state.previous == Regime.A


def test_determine_regime_hysteresis_prevents_switch(detector):
    """Not held long enough → no switch even if joint > threshold."""
    factors = FactorScores(SAD=0.8, PD=0.7, NCC=0.6)
    now = datetime.now(timezone.utc)
    current = RegimeState(
        current=Regime.A,
        previous=Regime.A,
        switched=False,
        held_since=now - timedelta(hours=1),  # Only 1 hour, need 24
        factor_scores=FactorScores(SAD=0.3, PD=0.3, NCC=0.3),
        joint_score=0.3,
        hysteresis=Hysteresis(
            enter_threshold=0.55, exit_threshold=0.40,
            min_hold="PT24H", time_in_current="PT1H",
        ),
    )
    state = detector.determine_regime(factors, current=current)
    assert state.current == Regime.A
    assert state.switched is False


def test_determine_regime_switch_b_to_a(detector):
    """Low score + held long enough → switch B back to A."""
    factors = FactorScores(SAD=0.1, PD=0.1, NCC=0.1)
    now = datetime.now(timezone.utc)
    current = RegimeState(
        current=Regime.B,
        previous=Regime.A,
        switched=False,
        held_since=now - timedelta(hours=48),
        factor_scores=FactorScores(SAD=0.8, PD=0.7, NCC=0.6),
        joint_score=0.72,
        hysteresis=Hysteresis(
            enter_threshold=0.55, exit_threshold=0.40,
            min_hold="PT24H", time_in_current="PT48H",
        ),
    )
    state = detector.determine_regime(factors, current=current)
    assert state.current == Regime.A
    assert state.switched is True
    assert state.previous == Regime.B
