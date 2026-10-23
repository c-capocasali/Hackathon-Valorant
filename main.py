"""Valorant Virtual Coach - entry point.

Usage:
    python main.py                         # run the PyQt overlay
    python main.py --mode console          # headless console fallback
    python main.py --mode web --port 8080  # web fallback (RNF02)
    python main.py --match path/to/match.json
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from src.data_engine import DataEngine
from src.simulator import MatchSimulator

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MATCHES = os.path.join(HERE, "data", "matches")
DEFAULT_MATCH = os.path.join(HERE, "data", "live_match.json")


def build_engine(matches_dir):
    print("Carregando base global de partidas...")
    engine = DataEngine(matches_dir)
    engine.build_global_data()
    print("  %d registros carregados" % len(engine.rounds_df))
    print("Treinando modelo de probabilidade de vitoria (XGBoost)...")
    engine.train_win_model()
    print("  modelo pronto")
    return engine


def run_console(engine, simulator):
    """Headless fallback: print the coach text to stdout (RNF02)."""
    player_id = simulator.players()[0].get("puuid")
    simulator.start()
    while True:
        if simulator.state == MatchSimulator.BUY_PHASE:
            advice = engine.buy_phase_advice(
                simulator.match, simulator.current_round, player_id)
            print()
            print("=" * 60)
            print(advice["text"])
            time.sleep(simulator.buy_seconds)
        elif simulator.state == MatchSimulator.ACTION_PHASE:
            print("--- FASE DE ACAO (overlay oculto) ---")
            time.sleep(simulator.action_seconds)
        elif simulator.state == MatchSimulator.MATCH_END:
            summary = engine.match_summary(simulator.match, player_id)
            print()
            print("=" * 60)
            print("RESUMO DA PARTIDA")
            for k, v in summary.items():
                if k != "economy_curve":
                    print("  %s = %s" % (k, v))
            break
        simulator.advance()


def run_web(engine, simulator, port):
    from src.fallback_web import FallbackWebServer
    server = FallbackWebServer(engine, simulator, port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def run_gui(engine, simulator):
    from PySide6.QtWidgets import QApplication
    from src.overlay_ui import CoachOverlay, CoachController
    from src.dashboard import PostMatchDashboard

    app = QApplication(sys.argv)
    overlay = CoachOverlay()

    def on_match_end(match, player_id):
        summary = engine.match_summary(match, player_id)
        dashboard = PostMatchDashboard(summary)
        dashboard.show()
        app._dashboard = dashboard  # keep a reference alive

    controller = CoachController(engine, simulator, overlay, on_match_end=on_match_end)
    controller.start()

    overlay.show_overlay()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="Valorant Virtual Coach")
    parser.add_argument("--matches-dir", default=DEFAULT_MATCHES,
                        help="directory with the championship JSON files")
    parser.add_argument("--match", default=DEFAULT_MATCH,
                        help="live match JSON used by the simulator")
    parser.add_argument("--mode", choices=["auto", "gui", "web", "console"],
                        default="auto")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--buy-seconds", type=float, default=8.0)
    parser.add_argument("--action-seconds", type=float, default=5.0)
    args = parser.parse_args()

    if not os.path.exists(args.match):
        sys.exit("Live match not found: %s" % args.match)

    engine = build_engine(args.matches_dir)
    simulator = MatchSimulator(args.match, args.buy_seconds, args.action_seconds)

    mode = args.mode
    if mode == "auto":
        mode = "gui"
        if os.environ.get("DISPLAY") is None and sys.platform != "win32":
            mode = "console"

    if mode == "console":
        run_console(engine, simulator)
    elif mode == "web":
        run_web(engine, simulator, args.port)
    else:
        try:
            run_gui(engine, simulator)
        except Exception as exc:
            print("GUI indisponivel (%s). Usando fallback console." % exc)
            run_console(engine, simulator)


if __name__ == "__main__":
    main()
