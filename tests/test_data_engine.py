"""Tests for the DataEngine (RF01..RF08) against the real dataset."""

import glob
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_engine import DataEngine  # noqa: E402

MATCHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "matches")


@pytest.fixture(scope="module")
def engine():
    eng = DataEngine(MATCHES_DIR)
    eng.build_global_data()
    eng.train_win_model()
    return eng


def _live_match():
    for f in sorted(glob.glob(os.path.join(MATCHES_DIR, "**", "*.json"), recursive=True)):
        d = json.load(open(f, encoding="utf-8"))
        if len(d["roundResults"]) >= 15:
            return d
    return None


def test_global_data_built(engine):
    assert engine.rounds_df is not None
    assert len(engine.rounds_df) > 1000


def test_weapon_winrate(engine):
    wr = engine.weapon_winrate()
    assert "Vandal" in wr.index
    assert 0.0 <= wr.loc["Vandal", "winrate"] <= 1.0


def test_site_stats_valid(engine):
    sites = engine.site_stats(map_name="Ascent")
    assert not sites.empty
    assert set(sites["plant_site"]).issubset({"A", "B", "C"})
    assert (sites["success_rate"] >= 0).all()


def test_opening_advice(engine):
    a = engine.opening_advice("Ascent", "Omen", "Attacker")
    assert a["best_weapon"]
    assert a["best_site"] in ("A", "B", "C")


def test_economy_advice(engine):
    assert engine.economy_advice(4500, True)["buy_type"] == "full"
    assert engine.economy_advice(500, False)["buy_type"] == "eco"


def test_win_probability_range(engine):
    feat = {"round_num": 3, "is_pistol": 0, "side_code": 1, "map_code": 0,
            "loadout": 20000, "spent": 18000, "remaining": 5000, "armor": 5000,
            "n_duelist": 2, "n_initiator": 1, "n_controller": 1, "n_sentinel": 1}
    p = engine.win_probability(feat)
    assert 0.0 <= p <= 1.0


def test_buy_phase_advice(engine):
    live = _live_match()
    assert live is not None
    puuid = live["players"][0]["puuid"]
    adv = engine.buy_phase_advice(live, 0, puuid)
    assert adv["text"]
    assert 0.0 <= adv["win_probability"] <= 1.0


def test_match_summary(engine):
    live = _live_match()
    puuid = live["players"][0]["puuid"]
    summary = engine.match_summary(live, puuid)
    assert summary["total_rounds"] > 0
    assert "economy_curve" in summary
    assert len(summary["economy_curve"]) == summary["total_rounds"]
