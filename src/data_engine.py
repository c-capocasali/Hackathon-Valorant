"""Core analysis engine for the Valorant Virtual Coach.

Loads the global championship database (the JSON files from the challenge
repository), builds a fast parquet cache, and implements every functional
requirement (RF01..RF08) plus the business rules (RN01..RN03).

Data schema (real Riot/Valorant match format):

    matchInfo  { mapId, matchId, ... }
    players    [ { puuid, teamId, characterId, gameName, ... } ]
    teams      [ { teamId, won, roundsWon, ... } ]
    roundResults [ {
        roundNum, roundResult, winningTeam, winningTeamRole,
        plantSite, plantLocation {x,y}, plantPlayerLocations [...],
        playerStats [ {
            puuid, score,
            economy { loadoutValue, weapon, armor, remaining, spent },
            damage  [ { receiver, damage, legshots, bodyshots, headshots } ],
            kills   [ { killer, victim, victimLocation {x,y},
                        playerLocations [ { puuid, viewRadians, location {x,y} } ] } ],
        } ]
    } ]
"""

from __future__ import annotations

import json
import math
import os
import glob
import pickle
from typing import Optional

import numpy as np
import pandas as pd

from . import game_data as gd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
FULL_BUY_THRESHOLD = 3900      # rifle (2900) + heavy armor (1000)
LOW_HS_THRESHOLD = 0.15        # RN02: trigger mechanical tips below 15% HS
LOW_HS_ROUNDS = 3              # RN02: ...sustained over 3 consecutive rounds
MIN_HITS_FOR_AIM = 30          # minimum hits before aim advice is given
FLANK_ANGLE_RAD = math.radians(110)        # killer >110deg behind == flank
CROSSHAIR_OFFSET_RAD = math.radians(10)    # crosshair placement threshold
MIN_WEAPON_SAMPLE = 20         # minimum uses before a weapon winrate is trusted

# Feature columns for the XGBoost win model (RF07). Pre-round features only:
# no post-round outcomes (kills/deaths/damage) to avoid target leakage.
FEATURE_COLS = [
    "round_num", "is_pistol", "side_code", "map_code",
    "loadout", "spent", "remaining", "armor",
    "n_duelist", "n_initiator", "n_controller", "n_sentinel",
]


def _angle_diff(a: float, b: float) -> float:
    """Signed shortest angular difference, normalized to [-pi, pi]."""
    d = (a - b) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return d


class DataEngine:
    """Loads and analyzes the global match database + the live match."""

    def __init__(
        self,
        matches_dir: str,
        cache_path: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        self.matches_dir = matches_dir
        self.cache_path = cache_path or os.path.join(matches_dir, "_cache", "global_rounds.parquet")
        self.model_path = model_path or os.path.join(matches_dir, "_cache", "win_model.pkl")

        self.rounds_df: Optional[pd.DataFrame] = None
        self.team_df: Optional[pd.DataFrame] = None
        self._model = None
        self._feature_cols: list = list(FEATURE_COLS)

    # ------------------------------------------------------------------ #
    # Data ingestion
    # ------------------------------------------------------------------ #
    def _extract_match(self, path: str) -> list:
        """Flatten one match JSON into a list of player-round records."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        match_id = data.get("matchInfo", {}).get("matchId", os.path.basename(path))
        map_name = gd.map_name(data.get("matchInfo", {}).get("mapId", ""))

        players = {}
        for p in data.get("players", []):
            players[p.get("puuid")] = {
                "team": p.get("teamId", "Unknown"),
                "agent": gd.agent_name(p.get("characterId", "")),
                "name": p.get("gameName", "?"),
            }

        records = []
        for rr in data.get("roundResults", []):
            round_num = rr.get("roundNum", 0)
            winning_team = rr.get("winningTeam")
            winning_role = rr.get("winningTeamRole")
            plant_site = rr.get("plantSite")
            plant_loc = rr.get("plantLocation") or {}
            plant_locs = rr.get("plantPlayerLocations") or []

            for ps in rr.get("playerStats", []):
                puuid = ps.get("puuid")
                pinfo = players.get(puuid, {})
                team = pinfo.get("team", "Unknown")

                eco = ps.get("economy") or {}
                weapon = gd.weapon_name(eco.get("weapon", ""))
                armor_uuid = eco.get("armor", "") or ""
                remaining = eco.get("remaining", 0)
                spent = eco.get("spent", 0)
                loadout = eco.get("loadoutValue", 0)

                dmg = ps.get("damage") or []
                head = sum(int(e.get("headshots", 0)) for e in dmg)
                body = sum(int(e.get("bodyshots", 0)) for e in dmg)
                leg = sum(int(e.get("legshots", 0)) for e in dmg)
                dealt = sum(int(e.get("damage", 0)) for e in dmg)

                kills_events = ps.get("kills") or []
                kills = sum(1 for k in kills_events if k.get("killer") == puuid)
                deaths = sum(1 for k in kills_events if k.get("victim") == puuid)

                # Infer the side (Attacker/Defender) from the winner role.
                if team == winning_team:
                    side = winning_role
                elif winning_role == "Attacker":
                    side = "Defender"
                else:
                    side = "Attacker"

                if round_num == 0:
                    buy_type = "pistol"
                elif spent <= 800:
                    buy_type = "eco"
                elif spent <= 2400:
                    buy_type = "half"
                else:
                    buy_type = "full"

                records.append({
                    "match_id": match_id,
                    "map": map_name,
                    "round_num": int(round_num),
                    "winning_team": winning_team,
                    "winning_role": winning_role,
                    "plant_site": plant_site,
                    "round_result": rr.get("roundResult"),
                    "plant_x": plant_loc.get("x"),
                    "plant_y": plant_loc.get("y"),
                    "n_plant_locs": len(plant_locs),
                    "puuid": puuid,
                    "team": team,
                    "side": side,
                    "agent": pinfo.get("agent", "Unknown"),
                    "player_name": pinfo.get("name", "?"),
                    "weapon": weapon,
                    "weapon_class": gd.weapon_class(weapon),
                    "weapon_cost": int(gd.weapon_cost(weapon)),
                    "armor": gd.armor_name(armor_uuid),
                    "armor_cost": int(gd.armor_cost(armor_uuid)),
                    "loadout_value": int(loadout),
                    "remaining": int(remaining),
                    "spent": int(spent),
                    "buy_type": buy_type,
                    "score": int(ps.get("score", 0)),
                    "kills": kills,
                    "deaths": deaths,
                    "headshots": head,
                    "bodyshots": body,
                    "legshots": leg,
                    "hits": head + body + leg,
                    "damage_dealt": dealt,
                    "won": 1 if team == winning_team else 0,
                })

        return records

    def build_global_data(self, force: bool = False) -> pd.DataFrame:
        """Build (or load) the player-round DataFrame from all match files."""
        cache_dir = os.path.dirname(self.cache_path)
        if not force and os.path.exists(self.cache_path):
            self.rounds_df = pd.read_parquet(self.cache_path)
            return self.rounds_df

        files = sorted(glob.glob(os.path.join(self.matches_dir, "**", "*.json"), recursive=True))
        if not files:
            raise FileNotFoundError("No match JSON files found under %s" % self.matches_dir)

        all_records = []
        for f in files:
            try:
                all_records.extend(self._extract_match(f))
            except Exception as exc:
                print("warn: skipped %s (%s)" % (f, exc))

        df = pd.DataFrame(all_records)
        os.makedirs(cache_dir, exist_ok=True)
        df.to_parquet(self.cache_path, index=False)
        self.rounds_df = df
        return df

    # ------------------------------------------------------------------ #
    # Aggregations over the global database
    # ------------------------------------------------------------------ #
    def weapon_winrate(self, map_name=None, round_type=None):
        df = self.rounds_df
        if map_name:
            df = df[df["map"] == map_name]
        if round_type == "pistol":
            df = df[df["round_num"] == 0]
        elif round_type:
            df = df[df["buy_type"] == round_type]
        g = df.groupby("weapon").agg(wins=("won", "sum"), games=("won", "count"))
        g["winrate"] = g["wins"] / g["games"]
        g["cost"] = g.index.map(gd.weapon_cost)
        g["class"] = g.index.map(gd.weapon_class)
        return g.sort_values("winrate", ascending=False)

    def agent_winrate(self, map_name=None):
        df = self.rounds_df
        if map_name:
            df = df[df["map"] == map_name]
        g = df.groupby("agent").agg(wins=("won", "sum"), games=("won", "count"))
        g["winrate"] = g["wins"] / g["games"]
        return g.sort_values("winrate", ascending=False)

    def site_stats(self, map_name=None):
        """Attack success rate per (map, plant site) and safe plant coords."""
        df = self.rounds_df[self.rounds_df["plant_site"].isin(["A", "B", "C"])]
        df = df[df["side"] == "Attacker"]
        if map_name:
            df = df[df["map"] == map_name]
        g = df.groupby(["map", "plant_site"]).agg(
            plants=("won", "count"),
            attacks_won=("won", "sum"),
            avg_x=("plant_x", "mean"),
            avg_y=("plant_y", "mean"),
        )
        g["success_rate"] = g["attacks_won"] / g["plants"]
        return g.reset_index().sort_values(["map", "success_rate"], ascending=False)

    def buy_type_stats(self):
        g = self.rounds_df.groupby("buy_type").agg(wins=("won", "sum"), games=("won", "count"))
        g["winrate"] = g["wins"] / g["games"]
        return g

    def global_hs_rate(self):
        hits = int(self.rounds_df["hits"].sum())
        heads = int(self.rounds_df["headshots"].sum())
        return heads / hits if hits else 0.0

    # ------------------------------------------------------------------ #
    # RF07 - XGBoost win-probability model
    # ------------------------------------------------------------------ #
    def _build_round_team_df(self):
        """One row per (match, round, team) with aggregated features."""
        df = self.rounds_df
        df = df.copy()
        df["role"] = df["agent"].map(gd.AGENT_ROLES).fillna("Unknown")
        roles = df.pivot_table(
            index=["match_id", "round_num", "team"],
            columns="role", values="won", aggfunc="count", fill_value=0,
        )
        roles = roles.reindex(columns=["Duelist", "Initiator", "Controller", "Sentinel"], fill_value=0)
        roles.columns = ["n_duelist", "n_initiator", "n_controller", "n_sentinel"]

        agg = df.groupby(["match_id", "round_num", "team", "map", "side"]).agg(
            loadout=("loadout_value", "sum"),
            spent=("spent", "sum"),
            remaining=("remaining", "sum"),
            armor=("armor_cost", "sum"),
            kills=("kills", "sum"),
            deaths=("deaths", "sum"),
            damage=("damage_dealt", "sum"),
            won=("won", "max"),
        ).reset_index()

        out = agg.merge(roles, left_on=["match_id", "round_num", "team"], right_index=True)
        out["is_pistol"] = (out["round_num"] == 0).astype(int)
        out["side_code"] = (out["side"] == "Attacker").astype(int)
        out["map_code"] = out["map"].astype("category").cat.codes
        return out

    def train_win_model(self, force=False):
        """Train the XGBoost round-win classifier (RF07)."""
        import xgboost as xgb

        if not force and self._model is not None:
            return self._model
        if not force and os.path.exists(self.model_path):
            with open(self.model_path, "rb") as fh:
                self._model = pickle.load(fh)
            return self._model

        team_df = self._build_round_team_df()
        self.team_df = team_df
        self._feature_cols = list(FEATURE_COLS)
        X = team_df[self._feature_cols]
        y = team_df["won"]

        self._model = xgb.XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
            random_state=42,
        )
        self._model.fit(X, y)

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "wb") as fh:
            pickle.dump(self._model, fh)
        return self._model

    def win_probability(self, features):
        """Predict the team round-win probability from a feature dict."""
        if self._model is None:
            self.train_win_model()
        row = pd.DataFrame([{c: features.get(c, 0) for c in self._feature_cols}])
        proba = self._model.predict_proba(row)[0]
        return float(proba[1])

    # ------------------------------------------------------------------ #
    # Live-match helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _armor_cost(name):
        return {"Heavy Armor": 1000, "Light Armor": 400,
                "Regen Shield": 650, "No Armor": 0}.get(name, 0)

    def _player_team(self, match, puuid):
        for p in match.get("players", []):
            if p.get("puuid") == puuid:
                return p.get("teamId", "Unknown")
        return "Unknown"

    def _player_agent(self, match, puuid):
        for p in match.get("players", []):
            if p.get("puuid") == puuid:
                return gd.agent_name(p.get("characterId", ""))
        return "Unknown"

    def _round_won_by(self, match, round_idx, puuid):
        rr = match["roundResults"][round_idx]
        return rr.get("winningTeam") == self._player_team(match, puuid)

    def _player_stat(self, rr, puuid):
        for ps in rr.get("playerStats", []):
            if ps.get("puuid") == puuid:
                return ps
        return {}

    def _pick_weapon(self, classes, max_cost, min_cost=0):
        wr = self.weapon_winrate()
        candidates = wr[(wr["class"].isin(classes)) & (wr["cost"] <= max_cost) & (wr["cost"] >= min_cost)]
        if not candidates.empty:
            return candidates.index[0]
        return "Classic"

    # ------------------------------------------------------------------ #
    # RF01 - Opening module (first round)
    # ------------------------------------------------------------------ #
    def opening_advice(self, map_name, agent, side):
        wr = self.weapon_winrate(map_name=map_name, round_type="pistol")
        affordable = wr[(wr["cost"] <= 800) & (wr["games"] >= MIN_WEAPON_SAMPLE)]
        if affordable.empty:
            affordable = wr[wr["cost"] <= 800]
        best_weapon = affordable.index[0] if len(affordable) else "Classic"

        sites = self.site_stats(map_name=map_name)
        best_site = sites["plant_site"].iloc[0] if len(sites) else None
        site_rate = sites["success_rate"].iloc[0] if len(sites) else 0.0

        ability = gd.RECOMMENDED_ABILITY.get(agent, "")
        role = gd.agent_role(agent)

        return {
            "map": map_name,
            "agent": agent,
            "role": role,
            "best_weapon": best_weapon,
            "best_ability": ability,
            "best_site": best_site,
            "site_success_rate": float(site_rate),
            "route": self._route_hint(map_name, best_site),
        }

    def _route_hint(self, map_name, site):
        if not site:
            return "Rotação padrão pelo meio do mapa."
        return ("Priorize a entrada no bomb %s pela rota principal; "
                "mantenha um lurker no corredor oposto." % site)

    # ------------------------------------------------------------------ #
    # RF02 - Economy / shop assistant
    # ------------------------------------------------------------------ #
    def economy_advice(self, remaining, prev_won):
        if prev_won is None:
            buy_type = "pistol"
            reason = "Round de pistola (abertura)."
        elif remaining >= FULL_BUY_THRESHOLD:
            buy_type = "full"
            reason = "Saldo suficiente para full-buy de rifle + armadura pesada."
        elif remaining >= 1800:
            buy_type = "half"
            reason = "Saldo parcial: force/half-buy para manter pressão sem quebrar a economia."
        else:
            buy_type = "eco"
            reason = "Saldo baixo: economize para um full-buy no próximo round."

        weapon, armor = self._best_loadout(buy_type, remaining)
        cost = int(gd.weapon_cost(weapon) + self._armor_cost(armor))
        return {
            "buy_type": buy_type,
            "remaining": int(remaining),
            "prev_won": prev_won,
            "reason": reason,
            "weapon": weapon,
            "armor": armor,
            "cost": cost,
        }

    def _best_loadout(self, buy_type, remaining):
        if buy_type == "pistol":
            return self._pick_weapon(["Pistols"], 500), "Light Armor"
        if buy_type == "eco":
            return self._pick_weapon(["Pistols"], max(remaining, 0)), "No Armor"
        if buy_type == "half":
            return self._pick_weapon(["SMGs", "Shotguns"], max(remaining - 400, 0)), "Light Armor"
        # Full buy: premium rifle (Phantom/Vandal/Warden) + heavy armor (meta).
        return self._pick_weapon(["Rifles"], max(remaining - 1000, 0), min_cost=2900), "Heavy Armor"

    # ------------------------------------------------------------------ #
    # RF03 - Spike positioning recommendation
    # ------------------------------------------------------------------ #
    def spike_recommendation(self, map_name, side):
        sites = self.site_stats(map_name=map_name)
        if sites.empty:
            return {"best_site": None, "success_rate": 0.0, "safe_coords": []}
        best = sites.iloc[0]
        coords = sites[sites["map"] == map_name][["plant_site", "avg_x", "avg_y", "success_rate"]]
        safe = []
        for _, row in coords.head(3).iterrows():
            if pd.notna(row["avg_x"]) and pd.notna(row["avg_y"]):
                safe.append({
                    "site": row["plant_site"],
                    "x": float(row["avg_x"]),
                    "y": float(row["avg_y"]),
                    "success_rate": float(row["success_rate"]),
                })
        return {
            "best_site": best["plant_site"],
            "success_rate": float(best["success_rate"]),
            "safe_coords": safe,
        }

    # ------------------------------------------------------------------ #
    # RF04 - Danger zones (heatmaps)
    # ------------------------------------------------------------------ #
    def danger_zones(self, match, up_to_round, puuid):
        deaths = []
        team = self._player_team(match, puuid)
        for rr in match["roundResults"][:up_to_round]:
            for ps in rr.get("playerStats", []):
                if ps.get("puuid") == puuid or self._player_team(match, ps.get("puuid")) == team:
                    for k in ps.get("kills", []):
                        if k.get("victim") == ps.get("puuid"):
                            v = k.get("victimLocation") or {}
                            if v.get("x") is not None and v.get("y") is not None:
                                deaths.append((int(v["x"]), int(v["y"])))
        if not deaths:
            return []
        buckets = {}
        for x, y in deaths:
            key = (x // 1000, y // 1000)
            buckets[key] = buckets.get(key, 0) + 1
        ranked = sorted(buckets.items(), key=lambda kv: -kv[1])[:5]
        return [{"cell_x": k[0] * 1000, "cell_y": k[1] * 1000, "deaths": c} for k, c in ranked]

    # ------------------------------------------------------------------ #
    # RF05 - Aim / headshot accuracy
    # ------------------------------------------------------------------ #
    def aim_adjustment(self, match, up_to_round, puuid):
        rounds = match["roundResults"][:up_to_round]
        recent = rounds[-LOW_HS_ROUNDS:] if len(rounds) >= LOW_HS_ROUNDS else rounds
        head = body = leg = 0
        for rr in recent:
            ps = self._player_stat(rr, puuid)
            for d in ps.get("damage", []):
                head += int(d.get("headshots", 0))
                body += int(d.get("bodyshots", 0))
                leg += int(d.get("legshots", 0))
        total = head + body + leg
        if total < MIN_HITS_FOR_AIM:
            return None
        hs_rate = head / total
        leg_rate = leg / total
        body_rate = body / total

        if hs_rate < LOW_HS_THRESHOLD:
            if leg_rate >= 0.30:
                direction, tip = "raise", "Levante a mira: muitos tiros acertando as pernas."
            else:
                direction, tip = "raise", "Levante a mira para a linha da cabeça."
        elif leg_rate >= 0.30 and body_rate >= 0.45:
            direction, tip = "raise", "Ajuste a mira um pouco para cima."
        elif hs_rate >= 0.35:
            direction, tip = "keep", "Mira bem calibrada. Mantenha o crosshair na altura da cabeça."
        else:
            direction, tip = "keep", "Mira dentro do esperado para o meta."

        return {
            "headshots": head, "bodyshots": body, "legshots": leg,
            "hs_rate": round(hs_rate, 3), "leg_rate": round(leg_rate, 3),
            "direction": direction, "tip": tip, "rounds_sampled": len(recent),
        }

    # ------------------------------------------------------------------ #
    # RF06 - Spatial awareness & crosshair placement
    # ------------------------------------------------------------------ #
    def spatial_advice(self, match, up_to_round, puuid):
        flank_deaths = 0
        deaths = 0
        offsets = []
        for rr in match["roundResults"][:up_to_round]:
            for ps in rr.get("playerStats", []):
                for k in ps.get("kills", []):
                    locs = k.get("playerLocations") or []
                    if k.get("victim") == puuid:
                        deaths += 1
                        p_loc = next((l for l in locs if l.get("puuid") == puuid), None)
                        k_loc = next((l for l in locs if l.get("puuid") == k.get("killer")), None)
                        if p_loc and k_loc:
                            px, py = p_loc["location"]["x"], p_loc["location"]["y"]
                            kx, ky = k_loc["location"]["x"], k_loc["location"]["y"]
                            angle = math.atan2(ky - py, kx - px)
                            diff = abs(_angle_diff(p_loc.get("viewRadians", 0.0), angle))
                            if diff > FLANK_ANGLE_RAD:
                                flank_deaths += 1
                    elif k.get("killer") == puuid:
                        v_loc = k.get("victimLocation") or {}
                        p_loc = next((l for l in locs if l.get("puuid") == puuid), None)
                        if p_loc and v_loc.get("x") is not None:
                            vx, vy = v_loc["x"], v_loc["y"]
                            px, py = p_loc["location"]["x"], p_loc["location"]["y"]
                            angle = math.atan2(vy - py, vx - px)
                            offsets.append(_angle_diff(p_loc.get("viewRadians", 0.0), angle))

        flank_rate = (flank_deaths / deaths) if deaths else 0.0
        mean_offset = float(np.mean(offsets)) if offsets else 0.0

        if flank_rate >= 0.5 and deaths >= 3:
            flank_tip = "Você está sendo flanqueado com frequência: cheque os ângulos traseiros e use utilidade de contenção."
        elif flank_rate >= 0.3:
            flank_tip = "Atenção a flancos: posicione-se com cobertura lateral."
        else:
            flank_tip = "Flancos sob controle."

        if abs(mean_offset) > CROSSHAIR_OFFSET_RAD and len(offsets) >= 5:
            if mean_offset > 0:
                cross_tip = "Crosshair deslocado para a direita; antecipe os ângulos de entrada."
            else:
                cross_tip = "Crosshair deslocado para a esquerda; antecipe os ângulos de entrada."
        else:
            cross_tip = "Crosshair placement alinhado aos ângulos de entrada."

        return {
            "deaths": deaths, "flank_deaths": flank_deaths,
            "flank_rate": round(flank_rate, 3),
            "mean_crosshair_offset_rad": round(mean_offset, 3),
            "flank_tip": flank_tip, "crosshair_tip": cross_tip,
        }

    # ------------------------------------------------------------------ #
    # RF08 - Post-match summary
    # ------------------------------------------------------------------ #
    def match_summary(self, match, puuid):
        team = self._player_team(match, puuid)
        map_name = gd.map_name(match.get("matchInfo", {}).get("mapId", ""))
        rounds = match.get("roundResults", [])

        economy_curve = []
        for rr in rounds:
            ps = self._player_stat(rr, puuid)
            eco = ps.get("economy") or {}
            economy_curve.append({
                "round": rr.get("roundNum", 0),
                "remaining": int(eco.get("remaining", 0)),
                "spent": int(eco.get("spent", 0)),
                "loadout_value": int(eco.get("loadoutValue", 0)),
            })

        total_head = total_body = total_leg = 0
        total_kills = total_deaths = 0
        for rr in rounds:
            ps = self._player_stat(rr, puuid)
            for d in ps.get("damage", []):
                total_head += int(d.get("headshots", 0))
                total_body += int(d.get("bodyshots", 0))
                total_leg += int(d.get("legshots", 0))
            for k in ps.get("kills", []):
                if k.get("killer") == puuid:
                    total_kills += 1
                if k.get("victim") == puuid:
                    total_deaths += 1

        hits = total_head + total_body + total_leg
        hs_rate = (total_head / hits) if hits else 0.0
        team_won = any(t.get("teamId") == team and t.get("won") for t in match.get("teams", []))
        score = next((t.get("numPoints", 0) for t in match.get("teams", []) if t.get("teamId") == team), 0)

        return {
            "map": map_name,
            "player_agent": self._player_agent(match, puuid),
            "team": team,
            "team_won": bool(team_won),
            "score": int(score),
            "kills": total_kills,
            "deaths": total_deaths,
            "hs_rate": round(hs_rate, 3),
            "headshots": total_head,
            "bodyshots": total_body,
            "legshots": total_leg,
            "global_hs_rate": round(self.global_hs_rate(), 3),
            "economy_curve": economy_curve,
            "total_rounds": len(rounds),
        }

    # ------------------------------------------------------------------ #
    # Orchestration: one call for the buy-phase coach text
    # ------------------------------------------------------------------ #
    def buy_phase_advice(self, match, round_index, puuid):
        map_name = gd.map_name(match.get("matchInfo", {}).get("mapId", ""))
        agent = self._player_agent(match, puuid)
        team = self._player_team(match, puuid)

        rr = match["roundResults"][round_index]
        ps = self._player_stat(rr, puuid)
        eco = ps.get("economy") or {}
        # Real Riot "remaining" is post-buy; pre-buy balance = remaining + spent.
        balance = int(eco.get("remaining", 0)) + int(eco.get("spent", 0))

        prev_won = None
        if round_index > 0:
            prev_won = self._round_won_by(match, round_index - 1, puuid)

        side = self._side_for_round(rr, team)

        advice = {
            "round_number": int(rr.get("roundNum", round_index)),
            "map": map_name,
            "agent": agent,
            "team": team,
            "side": side,
        }

        if round_index == 0:
            advice["opening"] = self.opening_advice(map_name, agent, side or "Attacker")
        else:
            advice["opening"] = None

        advice["economy"] = self.economy_advice(balance, prev_won)
        advice["spike"] = self.spike_recommendation(map_name, side or "Attacker")
        advice["danger_zones"] = self.danger_zones(match, round_index, puuid)
        advice["aim"] = self.aim_adjustment(match, round_index, puuid)
        advice["spatial"] = self.spatial_advice(match, round_index, puuid)
        advice["win_probability"] = self.win_probability(self._live_features(match, round_index, team, map_name))
        advice["text"] = self.format_coach_text(advice)
        return advice

    def _side_for_round(self, rr, team):
        winning_team = rr.get("winningTeam")
        winning_role = rr.get("winningTeamRole")
        if team == winning_team:
            return winning_role
        if winning_role == "Attacker":
            return "Defender"
        return "Attacker"

    def _live_features(self, match, round_index, team, map_name):
        rr = match["roundResults"][round_index]
        side = self._side_for_round(rr, team)

        role_count = {"Duelist": 0, "Initiator": 0, "Controller": 0, "Sentinel": 0}
        for p in match.get("players", []):
            if p.get("teamId") == team:
                ag = gd.agent_name(p.get("characterId", ""))
                r = gd.agent_role(ag)
                role_count[r] = role_count.get(r, 0) + 1

        loadout = spent = remaining = armor = 0
        for ps in rr.get("playerStats", []):
            if self._player_team(match, ps.get("puuid")) != team:
                continue
            eco = ps.get("economy") or {}
            loadout += int(eco.get("loadoutValue", 0))
            spent += int(eco.get("spent", 0))
            remaining += int(eco.get("remaining", 0))
            armor += gd.armor_cost(eco.get("armor", "") or "")

        return {
            "round_num": int(rr.get("roundNum", round_index)),
            "is_pistol": 1 if rr.get("roundNum", 0) == 0 else 0,
            "side_code": 1 if side == "Attacker" else 0,
            "map_code": self._map_code(map_name),
            "loadout": loadout,
            "spent": spent,
            "remaining": remaining,
            "armor": armor,
            "n_duelist": role_count.get("Duelist", 0),
            "n_initiator": role_count.get("Initiator", 0),
            "n_controller": role_count.get("Controller", 0),
            "n_sentinel": role_count.get("Sentinel", 0),
        }

    def _map_code(self, map_name):
        if self.team_df is not None and "map" in self.team_df.columns:
            cats = self.team_df["map"].astype("category").cat.categories
            codes = dict(zip(cats, range(len(cats))))
            return codes.get(map_name, 0)
        return 0

    # ------------------------------------------------------------------ #
    # Coach text formatting
    # ------------------------------------------------------------------ #
    def format_coach_text(self, advice):
        lines = []
        lines.append("ROUND %d - BUY PHASE" % advice.get("round_number", 0))
        if advice.get("opening"):
            o = advice["opening"]
            lines.append("[Abertura] Mapa %s, %s (%s)" % (o["map"], o["agent"], o["role"]))
            lines.append("  Arma: %s | Habilidade: %s" % (o["best_weapon"], o["best_ability"] or "-"))
            lines.append("  Bomb inicial: %s (sucesso %.0f%%)" % (o["best_site"], 100 * o["site_success_rate"]))
            lines.append("  Rota: %s" % o["route"])
        if advice.get("economy"):
            e = advice["economy"]
            lines.append("[Economia] %s" % e["buy_type"].upper())
            lines.append("  Saldo: %d | Arma: %s | Armadura: %s" % (e["remaining"], e["weapon"], e["armor"]))
            lines.append("  %s" % e["reason"])
        if advice.get("spike", {}).get("best_site"):
            s = advice["spike"]
            lines.append("[Spike] Plante no bomb %s (sucesso %.0f%%)" % (s["best_site"], 100 * s["success_rate"]))
            if s.get("safe_coords"):
                c = s["safe_coords"][0]
                lines.append("  Posição segura: (%d, %d)" % (c["x"], c["y"]))
        if advice.get("danger_zones"):
            dz = advice["danger_zones"][0]
            lines.append("[Perigo] Zona quente em (%d, %d) - %d abates" % (dz["cell_x"], dz["cell_y"], dz["deaths"]))
        if advice.get("aim"):
            lines.append("[Mira] %s (HS %.0f%%)" % (advice["aim"]["tip"], 100 * advice["aim"]["hs_rate"]))
        if advice.get("spatial"):
            lines.append("[Posição] %s" % advice["spatial"]["flank_tip"])
            lines.append("[Crosshair] %s" % advice["spatial"]["crosshair_tip"])
        lines.append("[Vitória] %.0f%% de chance de vitória no round" % (100 * advice.get("win_probability", 0.5)))
        return "\n".join(lines)
