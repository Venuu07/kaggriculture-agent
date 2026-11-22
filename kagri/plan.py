"""The daily plan: the action an agent submits each day, plus validation.

A plan is a plain dict (easy for an LLM to write as JSON):

    {
      "plant":      {"WHEAT": 6, "MELON": 4},   # new plots to sow today
      "sell":       {"WHEAT": "all", "EGG": 5}, # units to sell from the shed ("all" allowed)
      "buy_animals":{"GOOSE": 2},               # animals to buy (a coop/pasture is built for each)
      "fertilise":  ["MELON"],                  # crops to fertilise today (fertiliser bought if needed)
      "hands":      2,                          # farm hands to hire today
      "buy_land":   false,                      # unlock the next 5x5 quadrant
      "note":       "free text, ignored"
    }

Watering, harvesting, weeding, feeding and caring for animals are standing orders that the
Foreman always performs, so the agent only decides the economics.
"""
from __future__ import annotations

from typing import Any

from .engine import kaggriculture as kg

CROPS = list(kg.CROPS)
ANIMALS = list(kg.ANIMALS)
PRODUCTS = list(kg.PRODUCTS)
PLAN_KEYS = {"plant", "sell", "buy_animals", "fertilise", "hands", "buy_land", "note"}

HARVEST_AGE = {"WHEAT": 4, "CARROT": 3, "MELON": 10, "TOMATO": 11, "STRAWBERRY": 16}


def empty_plan() -> dict[str, Any]:
    """A do-nothing plan (the Foreman still waters, harvests and feeds)."""
    return {"plant": {}, "sell": {}, "buy_animals": {}, "fertilise": [], "hands": 0, "buy_land": False}


def hire_cost_total(n: int) -> int:
    """Total cost of hiring n hands in one day (Fibonacci pricing)."""
    return sum(kg._hire_cost(i) for i in range(n))


def validate_plan(plan: Any, state: dict[str, Any], max_hands: int = 6) -> tuple[dict[str, Any], list[str]]:
    """Clean a plan against the current farm state.

    Returns (clean_plan, rejections). Never raises: anything invalid is dropped or trimmed
    and a human-readable reason is added to `rejections`.
    """
    rej: list[str] = []
    clean = empty_plan()
    if not isinstance(plan, dict):
        return clean, [f"plan must be a JSON object, got {type(plan).__name__}"]

    for k in plan:
        if k not in PLAN_KEYS:
            rej.append(f"unknown plan key '{k}' ignored")

    cash = float(state["cash"])
    day = int(state["day"])
    last_day = int(state["last_day"])
    # Guardrail: keep enough cash to feed every animal (owned + new) for 3 days.
    wheat_price = float(state["prices"].get("WHEAT", 25))
    n_animals = sum(state.get("animals", {}).values())
    budget = cash - 3 * wheat_price * n_animals

    hands = _as_int(plan.get("hands", 0))
    if hands is None or hands < 0:
        rej.append("hands must be a non-negative integer; using 0")
        hands = 0
    if hands > max_hands:
        rej.append(f"hands capped at {max_hands}")
        hands = max_hands
    while hands > 0 and hire_cost_total(hands) > budget:
        hands -= 1
    clean["hands"] = hands
    budget -= hire_cost_total(hands)

    if plan.get("buy_land"):
        cost = state.get("next_land_cost")
        if cost is None:
            rej.append("buy_land rejected: all land already owned")
        elif cost > budget:
            rej.append(f"buy_land rejected: costs ${cost}, only ${budget:.0f} left")
        else:
            clean["buy_land"] = True
            budget -= cost

    free = int(state["free_plots"]) + (25 if clean["buy_land"] else 0)

    animals = plan.get("buy_animals") or {}
    if isinstance(animals, dict):
        for a, n in animals.items():
            a = str(a).upper()
            n = _as_int(n)
            if n == 0:
                continue
            if a not in ANIMALS or n is None or n < 0:
                rej.append(f"buy_animals: invalid entry {a}={n}")
                continue
            cost = kg.ANIMALS[a]["cost"]
            fit = min(n, max(0, free), max(0, int((budget - 3 * wheat_price * n) // cost)))
            if fit < n:
                rej.append(f"buy_animals {a}: trimmed {n}->{fit} (cash/space)")
            if fit > 0:
                clean["buy_animals"][a] = fit
                budget -= fit * cost + 3 * wheat_price * fit
                free -= fit
    else:
        rej.append("buy_animals must be an object like {\"GOOSE\": 1}")

    plant = plan.get("plant") or {}
    if isinstance(plant, dict):
        for c, n in plant.items():
            c = str(c).upper()
            n = _as_int(n)
            if n == 0:
                continue
            if c not in CROPS or n is None or n < 0:
                rej.append(f"plant: invalid entry {c}={n}")
                continue
            cd = kg.CROPS[c]
            ready_age = HARVEST_AGE[c] if not cd["ongoing"] else cd["first_yield_day"] + 1
            if day + ready_age > last_day:
                rej.append(f"plant {c} rejected: would not be ready before the season ends")
                continue
            seeds_have = int(state["seeds"].get(c, 0))
            need_buy = max(0, n - seeds_have)
            affordable = seeds_have + int(budget // cd["seed"])
            fit = max(0, min(n, free, affordable))
            if fit < n:
                rej.append(f"plant {c}: trimmed {n}->{fit} (free plots/cash)")
            if fit > 0:
                clean["plant"][c] = fit
                budget -= max(0, fit - seeds_have) * cd["seed"] if need_buy else 0
                free -= fit
    else:
        rej.append("plant must be an object like {\"WHEAT\": 4}")

    sell = plan.get("sell") or {}
    if isinstance(sell, dict):
        for item, q in sell.items():
            item = str(item).upper()
            have = int(state["shed"].get(item, 0))
            if item not in PRODUCTS:
                rej.append(f"sell: unknown product {item}")
                continue
            if isinstance(q, str) and q.lower() == "all":
                q = have
            q = _as_int(q)
            if q is None or q < 0:
                rej.append(f"sell {item}: quantity must be a number or 'all'")
                continue
            if q > have:
                rej.append(f"sell {item}: only {have} in shed, trimmed")
                q = have
            if q > 0:
                clean["sell"][item] = q
    else:
        rej.append("sell must be an object like {\"WHEAT\": \"all\"}")

    fert = plan.get("fertilise") or []
    if isinstance(fert, str):
        fert = [fert]
    if isinstance(fert, list):
        for c in fert:
            c = str(c).upper()
            if c in CROPS:
                if c not in clean["fertilise"]:
                    clean["fertilise"].append(c)
            else:
                rej.append(f"fertilise: unknown crop {c}")
    return clean, rej


def _as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
