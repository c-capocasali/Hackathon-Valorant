"""Web fallback interface (RNF02).

If the main overlay injection is detected and blocked by the anti-cheat
(Vanguard), the coach falls back to a web interface served over HTTP - usable
on a second monitor, on a phone on the local network, or in any browser
(out-of-focus window). It exposes the same advice produced by the DataEngine,
advancing the simulated match on a background thread.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .simulator import MatchSimulator

_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>Valorant Virtual Coach</title>
<style>
  body { background:#0f1218; color:#e8f4ff; font-family:Segoe UI,Roboto,sans-serif;
         display:flex; justify-content:center; padding-top:40px; }
  .panel { background:#12161f; border:1px solid #ff4655; border-radius:12px;
           padding:24px 30px; min-width:420px; max-width:640px; }
  h1 { color:#ff4655; font-size:18px; margin:0 0 14px; }
  pre { white-space:pre-wrap; font-family:Consolas,monospace; font-size:14px;
        line-height:1.5; margin:0; }
</style>
</head>
<body>
  <div class="panel">
    <h1>Valorant Virtual Coach</h1>
    <pre id="advice">Carregando...</pre>
  </div>
</body>
</html>
"""


class FallbackWebServer:
    """HTTP server + background simulation loop for the RNF02 fallback."""

    def __init__(self, engine, simulator: MatchSimulator, port: int = 8080):
        self.engine = engine
        self.simulator = simulator
        players = simulator.players()
        self.player_id = players[0].get("puuid") if players else None

        self.port = port
        self.advice_text = "Aguardando a partida..."
        self.summary = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._server = None

    # -- simulation loop ---------------------------------------------- #
    def _loop(self):
        self.simulator.start()
        self._refresh()
        while not self._stop.is_set():
            state, _round = self.simulator.advance()
            if state == MatchSimulator.ACTION_PHASE:
                with self._lock:
                    self.advice_text = "FASE DE ACAO - overlay oculto"
                self._sleep(self.simulator.action_seconds)
            elif state == MatchSimulator.BUY_PHASE:
                self._refresh()
                self._sleep(self.simulator.buy_seconds)
            elif state == MatchSimulator.MATCH_END:
                with self._lock:
                    self.summary = self.engine.match_summary(self.simulator.match, self.player_id)
                    self.advice_text = "PARTIDA ENCERRADA. Abra o dashboard."
                break

    def _refresh(self):
        advice = self.engine.buy_phase_advice(
            self.simulator.match, self.simulator.current_round, self.player_id)
        with self._lock:
            self.advice_text = advice["text"]

    def _sleep(self, seconds):
        self._stop.wait(seconds)

    # -- HTTP --------------------------------------------------------- #
    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/advice.json":
                    body = json.dumps({"text": server.advice_text,
                                       "summary": server.summary}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    body = _HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
        return Handler

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), self._handler())
        print("Fallback web at http://localhost:%d" % self.port)
        self._server.serve_forever()

    def stop(self):
        self._stop.set()
        if self._server:
            self._server.shutdown()
