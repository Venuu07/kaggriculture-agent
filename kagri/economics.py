"""Crop and market maths shared by tools and agents (uses the official price curves)."""
from __future__ import annotations

from typing import Any

from .engine import kaggriculture as kg
from .plan import HARVEST_AGE

ANIMAL_FEED_PER_DAY = 1


def sale_proceeds(item: str, qty: int, inventory: int) -> tuple[float, int]:
    """Money from selling `qty` units now, walking down the official price curve.

    Returns (total, final_price).
    """
    total = 0.0
    inv = inventory
    price = kg.market_price(item, inv)
    for _ in range(max(0, qty)):
        price = kg.market_price(item, inv)
        total += price
        if price > 1:
            inv += 1
    return total, kg.market_price(item, inv)


def crop_units(crop: str, fertilised: bool = False) -> int:
    """Expected harvest units per plot with daily watering."""
    cd = kg.CROPS[crop]
    if cd["ongoing"]:
        return cd["max_yield"] * (2 if fertilised else 1)
    window = cd["max_yield_day"] - (cd["max_yield_day"] + 1) // 2 + 1
    return min(cd["max_yield"], 1 + window * (2 if fertilised else 1))


def estimate_crop_profit(crop: str, obs: dict[str, Any], plots: int = 1) -> dict[str, Any]:
    """Expected profit of sowing `plots` plots of `crop` today, including price impact.

    Price impact counts the same crop already growing on our farm, because it will hit the
    market around the same time.
    """
    crop = crop.upper()
    if crop not in kg.CROPS:
        return {"error": f"unknown crop {crop}; choose from {list(kg.CROPS)}"}
    cd = kg.CROPS[crop]
    days = HARVEST_AGE[crop]
    ready_day = obs["day"] + days
    feasible = ready_day <= obs["last_day"]
    units = crop_units(crop) * plots
    already = obs["crops_growing"].get(crop, 0) * crop_units(crop) + obs["shed"].get(crop, 0)
    inv = obs["market_inventory"][crop]
    # Town demand drains roughly (days until sale) units/day per consuming shop + town centre.
    demand = days * (1 + 6 * sum(crop in kg.SHOPS[s] for s in obs["town_shops"]))
    start_inv = max(0, inv - demand)
    before, _ = sale_proceeds(crop, already, start_inv)
    after, end_price = sale_proceeds(crop, already + units, start_inv)
    revenue = after - before
    cost = cd["seed"] * plots
    profit = revenue - cost
    return {
        "crop": crop, "plots": plots, "days_to_harvest": days, "ready_day": ready_day,
        "feasible": feasible, "expected_units": units, "seed_cost": cost,
        "expected_revenue": round(revenue, 1), "expected_profit": round(profit, 1),
        "profit_per_plot_day": round(profit / max(1, plots * days), 1),
        "avg_sale_price": round(revenue / max(1, units), 1), "price_after_glut": end_price,
        "current_price": obs["prices"][crop],
    }


def estimate_animal_profit(animal: str, obs: dict[str, Any]) -> dict[str, Any]:
    """Expected profit of buying one animal today until the season ends."""
    animal = animal.upper()
    if animal not in kg.ANIMALS:
        return {"error": f"unknown animal {animal}; choose from {list(kg.ANIMALS)}"}
    a = kg.ANIMALS[animal]
    days_left = obs["last_day"] - obs["day"]
    productive = max(0, days_left - a["first_yield_day"])
    units = productive // a["interval"]
    product_price = obs["prices"][a["product"]]
    fert_units = max(0, days_left - 1)
    revenue = units * product_price * 0.85 + fert_units * obs["prices"]["FERTILIZER"] * 0.7
    feed = days_left * obs["prices"]["WHEAT"]
    profit = revenue - feed - a["cost"]
    return {"animal": animal, "product": a["product"], "days_left": days_left,
            "expected_product_units": units, "expected_fertiliser_units": fert_units,
            "feed_cost": round(feed), "cost": a["cost"], "expected_profit": round(profit, 1),
            "note": "every animal also drops 1 fertiliser/day (sells ~$100 or boosts crops)"}
