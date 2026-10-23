"""Transparent overlay UI + state machine (RNF01, RNF04, Execution Flow).

The overlay is a frameless, always-on-top window with a translucent background
and mouse passthrough so it never steals clicks from the game (RNF01). It is
shown only during the buy phase and hidden as soon as the round barriers drop
(RNF04), driven by the state machine below (States 0..3).

The state machine is decoupled from the heavy analysis: a QTimer drives the
MatchSimulator and the DataEngine produces the coach text for each buy phase.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QObject
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QFont

from .simulator import MatchSimulator

# Rounded semi-transparent panel so the text is readable while the window
# itself stays truly translucent (WA_TranslucentBackground).
_PANEL_STYLE = (
    "QLabel {"
    " background-color: rgba(12, 14, 22, 210);"
    " color: #e8f4ff;"
    " border: 1px solid rgba(255, 70, 85, 160);"
    " border-radius: 12px;"
    " padding: 14px 18px;"
    "}"
)


class CoachOverlay(QWidget):
    """Frameless, translucent, click-through coach panel."""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # RNF01
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = QLabel("AGUARDANDO PARTIDA...")
        self._label.setFont(QFont("Segoe UI", 10))
        self._label.setStyleSheet(_PANEL_STYLE)
        self._label.setTextFormat(Qt.TextFormat.PlainText)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self._label)

        self.resize(460, 300)
        # Position in a "clean" corner area (bottom-left) of the primary screen.
        self._position_clean_area()

    def _position_clean_area(self):
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.left() + 60, geo.bottom() - self.height() - 60)

    def set_text(self, text: str):
        self._label.setText(text)

    def show_overlay(self):
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()


class CoachController(QObject):
    """Drives the buy/action/match-end state machine with a QTimer."""

    def __init__(self, engine, simulator: MatchSimulator, overlay: CoachOverlay,
                 on_match_end=None):
        super().__init__()
        self.engine = engine
        self.sim = simulator
        self.overlay = overlay
        self.on_match_end = on_match_end

        players = simulator.players()
        self.player_id = players[0].get("puuid") if players else None

        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self.sim.start()
        self._enter_buy_phase()

    # -- phases -------------------------------------------------------- #
    def _enter_buy_phase(self):
        round_idx = self.sim.current_round
        advice = self.engine.buy_phase_advice(self.sim.match, round_idx, self.player_id)
        self.overlay.set_text(advice["text"])
        self.overlay.show_overlay()
        self._timer.start(int(self.sim.buy_seconds * 1000))

    def _enter_action_phase(self):
        self.overlay.hide_overlay()
        self._timer.start(int(self.sim.action_seconds * 1000))

    def _enter_match_end(self):
        self._timer.stop()
        self.overlay.hide_overlay()
        if self.on_match_end is not None:
            self.on_match_end(self.sim.match, self.player_id)

    # -- tick ---------------------------------------------------------- #
    def _tick(self):
        state, _round = self.sim.advance()
        if state == MatchSimulator.ACTION_PHASE:
            self._enter_action_phase()
        elif state == MatchSimulator.BUY_PHASE:
            self._enter_buy_phase()
        elif state == MatchSimulator.MATCH_END:
            self._enter_match_end()

    def stop(self):
        self._timer.stop()
        self.overlay.hide_overlay()
