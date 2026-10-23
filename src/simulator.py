"""Match simulator (mock) for testing UI reactivity.

Loads a static JSON match and "releases" its data one round at a time so the
overlay/state-machine can be exercised without a live game. The simulator is a
pure state machine; timing is driven externally (by the QTimer in overlay_ui
or by a test harness) via the advance() method.

Execution flow (per the requirements doc):

    State 0 (IDLE)         -> waiting for the match to start
    State 1 (BUY_PHASE)    -> overlay visible, coach processes the round
    State 2 (ACTION_PHASE) -> overlay hidden
    State 3 (MATCH_END)    -> open the post-match dashboard
"""

from __future__ import annotations

import json
from typing import Optional


class MatchSimulator:
    IDLE = 0
    BUY_PHASE = 1
    ACTION_PHASE = 2
    MATCH_END = 3

    def __init__(self, match_path: str, buy_seconds: float = 8.0,
                 action_seconds: float = 5.0):
        with open(match_path, "r", encoding="utf-8") as fh:
            self.match = json.load(fh)
        self.buy_seconds = buy_seconds
        self.action_seconds = action_seconds
        self.current_round: int = -1   # -1 == idle (before first round)
        self.state: int = self.IDLE

    # -- info ---------------------------------------------------------- #
    @property
    def total_rounds(self) -> int:
        return len(self.match.get("roundResults", []))

    @property
    def map_name(self) -> str:
        from . import game_data as gd
        return gd.map_name(self.match.get("matchInfo", {}).get("mapId", ""))

    def players(self) -> list:
        return self.match.get("players", [])

    def current_round_data(self) -> Optional[dict]:
        if 0 <= self.current_round < self.total_rounds:
            return self.match["roundResults"][self.current_round]
        return None

    # -- state transitions --------------------------------------------- #
    def start(self) -> int:
        """Begin the match: enter the first buy phase."""
        self.current_round = 0
        self.state = self.BUY_PHASE
        return self.state

    def advance(self) -> tuple:
        """Advance the state machine. Returns (state, current_round)."""
        if self.state == self.IDLE:
            self.start()
        elif self.state == self.BUY_PHASE:
            self.state = self.ACTION_PHASE
        elif self.state == self.ACTION_PHASE:
            self.current_round += 1
            if self.current_round >= self.total_rounds:
                self.state = self.MATCH_END
            else:
                self.state = self.BUY_PHASE
        return self.state, self.current_round
