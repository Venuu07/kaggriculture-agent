"""Building blocks for smart plans: glut-aware crop mix, sell sizing, animals, labour.

Used by the offline reasoner (no-LLM mode) and as the safe fallback when an LLM reply is unusable.
"""
from __future__ import annotations

import math
from typing import Any

from ..economics import crop_units, estimate_animal_profit, estimate_crop_profit, sale_proceeds
from ..engine import kaggriculture as kg

PREMIUM = {"MELON", "STRAWBERRY", "MILK", "WOOL"}


def crop_mix(obs: dict[str, Any], plots: int, params: dict[str, float] | None = None) -> dict[str, int]:
    """Allocate `plots` free plots one at a time to the crop with the best *marginal* profit per
    plot-day, so each extra plot of the same crop accounts for the price drop it causes."""
    params = params or {}
    counts = {c: 0 for c in kg.CROPS}
    cache: dict[tuple[str, int], float] = {}

    def profit(crop: str, n: int) -> float:
        if (crop, n) not in cache:
            cache[(crop, n)] = estimate_crop_profit(crop, obs, n)["expected_profit"] if n else 0.0
        return cache[(crop, n)]

    for _ in range(plots):
        best, best_val = None, params.get("min_margin", 2.0)
        for crop in kg.CROPS:
            est = estimate_crop_profit(crop, obs, 1)
            if not est["feasible"]:
                continue
            marginal = (profit(crop, counts[crop] + 1) - profit(crop, counts[crop])) / est["days_to_harvest"]
            marginal *= params.get(f"bias_{crop}", 1.0)
            if marginal > best_val:
                best, best_val = crop, marginal
        if best is None:
            break
        counts[best] += 1
    return {c: n for c, n in counts.items() if n}


def sell_orders(obs: dict[str, Any], floor_frac: float = 0.65) -> dict[str, Any]:
    """Sell staples freely; sell premium goods only while the price stays above `floor_frac` x base.
    Everything goes on the last two days, or when the shed is close to full."""
    out: dict[str, Any] = {}
    endgame = obs["days_left"] <= 1
    shed_full = obs["shed_capacity_left"] < 25
    for item, have in obs["shed"].items():
        if item not in kg.PRODUCTS or have <= 0:
            continue
        if item == "WHEAT" and obs["animals"]:
            have = max(0, have - 2 * sum(obs["animals"].values()))
        if item == "FERTILIZER" and obs.get("_keep_fertiliser"):
            have = max(0, have - obs["_keep_fertiliser"])
        if have <= 0:
            continue
        if endgame or shed_full:
            out[item] = have
            continue
        base = kg.MARKET_PARAMS[item]["base"]
        inv = obs["market_inventory"][item]
        qty = 0
        while qty < have and kg.market_price(item, inv + qty) >= floor_frac * base:
            qty += 1
        if item not in PREMIUM and obs["prices"][item] >= 0.5 * base:
            qty = have
        if qty:
            out[item] = qty
    return out


MAX_HANDS = 10


def hands_needed(obs: dict[str, Any], new_plots: int) -> int:
    """About one helper per 6 tiles that need daily work (the farmer handles items).
    Hands are cheap (Fibonacci: 10 hands cost $143/day), dead plants are not."""
    work = sum(obs["crops_growing"].values()) + new_plots + sum(obs["animals"].values()) + obs["weeds"]
    return max(0, min(MAX_HANDS, math.ceil(work / 6)))


def animal_purchase(obs: dict[str, Any], cash_after: float, max_new: int = 6) -> dict[str, int]:
    """Buy the most profitable animal while it pays back before the season ends."""
    best = max(kg.ANIMALS, key=lambda a: estimate_animal_profit(a, obs)["expected_profit"])
    est = estimate_animal_profit(best, obs)
    if est["expected_profit"] < 600:
        return {}
    cost = kg.ANIMALS[best]["cost"] + 4 * obs["prices"]["WHEAT"]
    n = int(min(max_new, cash_after // cost, obs["free_plots"]))
    return {best: n} if n > 0 else {}


def fertiliser_targets(obs: dict[str, Any]) -> list[str]:
    """Crops worth fertilising: always strawberries/tomatoes (yield doubles); melons when
    fertiliser is cheap or already in the shed (harvest 2 days earlier)."""
    have = obs["shed"].get("FERTILIZER", 0)
    targets = []
    for crop in ("STRAWBERRY", "TOMATO", "MELON"):
        if obs["crops_growing"].get(crop):
            if crop != "MELON" or have > 0 or obs["prices"]["FERTILIZER"] < 70:
                targets.append(crop)
    return targets


def strategic_plan(obs: dict[str, Any], params: dict[str, float] | None = None,
                   land: bool = True, animals: bool = True) -> dict[str, Any]:
    """A complete, sensible daily plan built from the helpers above."""
    params = params or {}
    plan: dict[str, Any] = {"plant": {}, "sell": {}, "fertilise": [], "hands": 0}
    cash = obs["cash"]
    plots = obs["free_plots"]
    reserve = params.get("cash_reserve", 150)
    if (land and obs["next_land_cost"] and obs["days_left"] >= params.get("land_min_days", 12)
            and cash - obs["next_land_cost"] >= params.get("land_buffer", 600)):
        plan["buy_land"] = True
        cash -= obs["next_land_cost"]
        plots += 25
    if animals and obs["days_left"] >= params.get("animal_min_days", 12):
        budget = cash * params.get("animal_share", 0.35) - reserve
        plan["buy_animals"] = animal_purchase(obs, budget, int(params.get("max_new_animals", 4)))
        n_new = sum(plan["buy_animals"].values())
        cash -= sum(kg.ANIMALS[a]["cost"] * n for a, n in plan["buy_animals"].items())
        plots -= n_new
    mix = crop_mix(obs, max(0, plots), params)
    spend = 0.0
    for crop, n in sorted(mix.items(), key=lambda kv: -estimate_crop_profit(kv[0], obs, kv[1])["profit_per_plot_day"]):
        seed = kg.CROPS[crop]["seed"]
        k = int(min(n, max(0, (cash - reserve - spend) // seed)))
        if k > 0:
            plan["plant"][crop] = k
            spend += k * seed
    plan["sell"] = sell_orders(obs, params.get("sell_floor", 0.65))
    plan["fertilise"] = fertiliser_targets(obs)
    plan["hands"] = min(MAX_HANDS, hands_needed(obs, sum(plan["plant"].values()) + sum(plan.get("buy_animals", {}).values()))
                        + int(params.get("hands_bonus", 0)))
    return plan


def expected_units_note(crop: str) -> int:
    return crop_units(crop)


__all__ = ["crop_mix", "sell_orders", "hands_needed", "animal_purchase", "fertiliser_targets",
           "strategic_plan", "sale_proceeds"]
