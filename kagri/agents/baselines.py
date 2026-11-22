"""Baseline agents that give the 'before' numbers."""
from __future__ import annotations

import math
import random
from typing import Any

from ..economics import estimate_crop_profit
from ..engine import kaggriculture as kg
from ..env import FarmEnv
from .base import Agent, Decision


class RandomAgent(Agent):
    """Random but legal-looking daily plans."""

    name = "random"
    label = "Random"

    def begin_episode(self, seed: int) -> None:
        self.rng = random.Random(seed + 999)

    def decide(self, obs: dict[str, Any], env: FarmEnv) -> Decision:
        r = self.rng
        plan: dict[str, Any] = {"plant": {}, "sell": {}, "hands": r.randint(0, 4)}
        if obs["free_plots"] and r.random() < 0.6:
            plan["plant"][r.choice(list(kg.CROPS))] = r.randint(1, obs["free_plots"])
        for item in obs["shed"]:
            if item in kg.PRODUCTS and r.random() < 0.5:
                plan["sell"][item] = "all"
        if r.random() < 0.05:
            plan["buy_land"] = True
        if r.random() < 0.05:
            plan["buy_animals"] = {r.choice(list(kg.ANIMALS)): 1}
        if obs["days_left"] <= 1:
            plan["sell"] = {k: "all" for k in obs["shed"] if k in kg.PRODUCTS}
        return Decision(plan=plan, trace=[{"type": "thought", "text": "Random choice."}])


class GreedyAgent(Agent):
    """Classic heuristic: plant the crop with the best margin per plot-day on every free plot,
    hire enough hands to water, sell whenever the price is at or above its running average."""

    name = "greedy"
    label = "Greedy heuristic"

    def decide(self, obs: dict[str, Any], env: FarmEnv) -> Decision:
        best, best_margin = None, -math.inf
        for crop in kg.CROPS:
            est = estimate_crop_profit(crop, obs, plots=1)
            # Greedy looks at a single plot in isolation: it ignores its own glut.
            margin = (obs["prices"][crop] * est["expected_units"] - kg.CROPS[crop]["seed"]) / est["days_to_harvest"]
            if est["feasible"] and margin > best_margin:
                best, best_margin = crop, margin
        plan: dict[str, Any] = {"plant": {}, "sell": {}}
        if best and obs["free_plots"]:
            plan["plant"][best] = obs["free_plots"]
        plots = sum(obs["crops_growing"].values()) + obs["free_plots"]
        plan["hands"] = min(6, math.ceil(plots / 8))
        hist = env.price_history
        for item in obs["shed"]:
            if item not in kg.PRODUCTS:
                continue
            avg = sum(h[item] for h in hist) / len(hist)
            if obs["prices"][item] >= avg or obs["days_left"] <= 2:
                plan["sell"][item] = "all"
        text = f"Best margin crop is {best} (${best_margin:.0f}/plot/day at today's price); plant all free plots."
        return Decision(plan=plan, trace=[{"type": "thought", "text": text}])
