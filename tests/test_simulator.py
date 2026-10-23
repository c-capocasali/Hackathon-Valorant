"""Tests for the MatchSimulator state machine (Execution Flow)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulator import MatchSimulator  # noqa: E402

MATCHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "matches")


def _any_match():
    import glob
    for f in sorted(glob.glob(os.path.join(MATCHES_DIR, "**", "*.json"), recursive=True)):
        d = json.load(open(f, encoding="utf-8"))
        if len(d["roundResults"]) >= 5:
            return f
    return None


def test_state_machine_flow():
    path = _any_match()
    assert path is not None
    sim = MatchSimulator(path, buy_seconds=0.01, action_seconds=0.01)

    assert sim.state == MatchSimulator.IDLE
    sim.start()
    assert sim.state == MatchSimulator.BUY_PHASE
    assert sim.current_round == 0

    sim.advance()
    assert sim.state == MatchSimulator.ACTION_PHASE
    assert sim.current_round == 0

    sim.advance()
    assert sim.state == MatchSimulator.BUY_PHASE
    assert sim.current_round == 1


def test_runs_to_match_end():
    path = _any_match()
    sim = MatchSimulator(path, buy_seconds=0.01, action_seconds=0.01)
    sim.start()
    states = [sim.state]
    for _ in range(1000):
        state, _ = sim.advance()
        states.append(state)
        if state == MatchSimulator.MATCH_END:
            break
    assert states[-1] == MatchSimulator.MATCH_END
