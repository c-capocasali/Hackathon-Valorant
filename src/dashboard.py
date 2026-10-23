"""Post-match dashboard (RF08).

Consolidated window showing performance statistics, economy evolution and
general charts generated from every metric computed during the match.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtGui import QFont


class _StatBox(QFrame):
    def __init__(self, title: str, value: str):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        t = QLabel(title)
        t.setStyleSheet("color: #8fa3b8; font-size: 11px;")
        v = QLabel(value)
        v.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        v.setStyleSheet("color: #e8f4ff;")
        layout.addWidget(t)
        layout.addWidget(v)


class PostMatchDashboard(QWidget):
    def __init__(self, summary: dict):
        super().__init__()
        self.setWindowTitle("Valorant Virtual Coach - Resumo da Partida")
        self.resize(860, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        # -- header --------------------------------------------------- #
        header = QLabel(
            "RESUMO DA PARTIDA  -  %s  (%s)" % (summary["map"], summary["player_agent"])
        )
        header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.setStyleSheet("color: #ff4655;")
        root.addWidget(header)

        result = "VITORIA" if summary["team_won"] else "DERROTA"
        res_label = QLabel("Resultado: %s  |  Placar: %d  |  Time: %s"
                           % (result, summary["score"], summary["team"]))
        res_label.setStyleSheet("color: #e8f4ff; font-size: 12px;")
        root.addWidget(res_label)

        # -- stat boxes ------------------------------------------------ #
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(_StatBox("Kills", str(summary["kills"])))
        row.addWidget(_StatBox("Deaths", str(summary["deaths"])))
        kd = (summary["kills"] / summary["deaths"]) if summary["deaths"] else float(summary["kills"])
        row.addWidget(_StatBox("K/D", "%.2f" % kd))
        row.addWidget(_StatBox("HS %%", "%.0f%%" % (100 * summary["hs_rate"])))
        row.addWidget(_StatBox("HS %% global", "%.0f%%" % (100 * summary["global_hs_rate"])))
        row.addWidget(_StatBox("Rounds", str(summary["total_rounds"])))
        root.addLayout(row)

        # -- chart ----------------------------------------------------- #
        self.canvas = FigureCanvas(self._build_figure(summary))
        root.addWidget(self.canvas, 1)

    def _build_figure(self, summary: dict) -> Figure:
        fig = Figure(figsize=(8, 4.2), tight_layout=True)
        fig.patch.set_facecolor("#12161f")

        curve = summary["economy_curve"]
        rounds = [c["round"] for c in curve]
        remaining = [c["remaining"] for c in curve]
        spent = [c["spent"] for c in curve]
        loadout = [c["loadout_value"] for c in curve]

        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor("#12161f")
        ax1.plot(rounds, remaining, marker="o", color="#4fc3f7", label="Saldo")
        ax1.plot(rounds, spent, marker="s", color="#ffb74d", label="Gasto")
        ax1.set_title("Evolucao da Economia", color="#e8f4ff", fontsize=10)
        ax1.set_xlabel("Round", color="#8fa3b8")
        ax1.set_ylabel("Credits", color="#8fa3b8")
        ax1.tick_params(colors="#8fa3b8")
        ax1.legend(facecolor="#1a1f2b", labelcolor="#e8f4ff", fontsize=8)
        ax1.grid(True, alpha=0.15)

        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor("#12161f")
        labels = ["Cabeca", "Corpo", "Pernas"]
        values = [summary["headshots"], summary["bodyshots"], summary["legshots"]]
        colors = ["#ff4655", "#4fc3f7", "#ffb74d"]
        ax2.bar(labels, values, color=colors)
        ax2.set_title("Distribuicao de Tiros", color="#e8f4ff", fontsize=10)
        ax2.tick_params(colors="#8fa3b8")
        ax2.grid(True, axis="y", alpha=0.15)

        return fig
