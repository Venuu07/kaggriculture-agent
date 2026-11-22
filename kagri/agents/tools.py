"""Tools the agent can call. Each returns a small JSON-friendly dict."""
from __future__ import annotations

import json
from typing import Any, Callable

from ..economics import estimate_animal_profit, estimate_crop_profit, sale_proceeds
from ..engine import kaggriculture as kg
from ..env import FarmEnv
from .strategy import crop_mix, strategic_plan

FOLLOW_UP_POLICY = "after today, the simulator keeps planting a glut-aware crop mix and selling (no new land/animals)"


class ToolBox:
    """Binds the tools to the live environment for one decision."""

    def __init__(self, env: FarmEnv, obs: dict[str, Any]) -> None:
        self.env = env
        self.obs = obs
        self.tools: dict[str, tuple[str, str, Callable[..., Any]]] = {
            "get_farm_state": ("Cash, free plots, crops growing, animals, shed stock, land, opponent cash.",
                               "{}", self.get_farm_state),
            "get_weather_forecast": ("Today's weather/events and a noisy forecast for the next days.",
                                     "{}", self.get_weather_forecast),
            "get_market_prices": ("Current sell prices, their recent history and town demand (shops).",
                                  '{"history_days": 5}', self.get_market_prices),
            "estimate_crop_profit": ("Expected profit of sowing N plots of a crop today, including the price "
                                     "drop our own harvest causes.", '{"crop": "MELON", "plots": 10}',
                                     self.estimate_crop_profit),
            "estimate_animal_profit": ("Expected profit of buying one animal now until season end.",
                                       '{"animal": "GOOSE"}', self.estimate_animal_profit),
            "estimate_sale": ("Money from selling N units of a product right now (walks the price curve).",
                              '{"item": "MELON", "qty": 20}', self.estimate_sale),
            "plan_crop_mix": ("Suggest a glut-aware crop mix for N plots (marginal profit per plot-day).",
                              '{"plots": 25}', self.plan_crop_mix),
            "simulate_action": ("Look-ahead: play a candidate plan today on a COPY of the farm, then "
                                f"{FOLLOW_UP_POLICY}; returns net-worth change.",
                                '{"plan": {...}, "days": 5}', self.simulate_action),
        }

    def describe(self, allowed: list[str] | None = None) -> str:
        lines = []
        for name, (desc, args, _) in self.tools.items():
            if allowed is None or name in allowed:
                lines.append(f"- {name}(args={args}): {desc}")
        lines.append('- take_action(args={"plan": {...}}): commit the final plan for today (ends your turn).')
        return "\n".join(lines)

    def call(self, name: str, args: Any) -> dict[str, Any]:
        if name not in self.tools:
            return {"error": f"unknown tool '{name}'. Available: {list(self.tools)} or take_action"}
        if not isinstance(args, dict):
            args = {}
        try:
            return self.tools[name][2](**args)
        except TypeError as e:
            return {"error": f"bad arguments for {name}: {e}"}
        except Exception as e:  # a tool must never crash the agent
            return {"error": f"{name} failed: {type(e).__name__}: {e}"}

    # ---------------------------------------------------------------- tools
    def get_farm_state(self) -> dict[str, Any]:
        o = self.obs
        keys = ["day", "days_left", "cash", "profit", "opponent_cash", "free_plots", "weeds", "crops_growing",
                "animals", "shed", "shed_capacity_left", "seeds", "land_quadrants", "next_land_cost"]
        out = {k: o[k] for k in keys}
        ready = [p for p in o["plots"] if p["ready_in"] == 0]
        out["plots_ready_to_harvest"] = len(ready)
        return out

    def get_weather_forecast(self) -> dict[str, Any]:
        return {"today": self.obs["weather"], "forecast": self.obs["forecast"],
                "effects": {"heavy_rain": "free watering", "drought": "unwatered plants die tonight (hire hands)",
                            "pests": "random, kill ~15% of unfertilised plants", "price_shock": "sudden glut/shortage"}}

    def get_market_prices(self, history_days: int = 5) -> dict[str, Any]:
        hist = self.env.price_history[-max(1, int(history_days)) - 1:]
        out = {}
        for item, price in self.obs["prices"].items():
            series = [h[item] for h in hist]
            base = kg.MARKET_PARAMS[item]["base"]
            out[item] = {"price": price, "base": base, "history": series,
                         "vs_base_pct": round(100 * price / base)}
        demand: dict[str, int] = {}
        for shop in self.obs["town_shops"]:
            for item in kg.SHOPS[shop]:
                demand[item] = demand.get(item, 0) + 6 * (2 if len(kg.SHOPS[shop]) == 1 else 1)
        return {"prices": out, "town_shops": self.obs["town_shops"], "shop_demand_units_per_day": demand}

    def estimate_crop_profit(self, crop: str, plots: int = 1) -> dict[str, Any]:
        return estimate_crop_profit(crop, self.obs, max(1, int(plots)))

    def estimate_animal_profit(self, animal: str) -> dict[str, Any]:
        return estimate_animal_profit(animal, self.obs)

    def estimate_sale(self, item: str, qty: int) -> dict[str, Any]:
        item = str(item).upper()
        if item not in kg.PRODUCTS:
            return {"error": f"unknown product {item}"}
        total, end = sale_proceeds(item, int(qty), self.obs["market_inventory"][item])
        return {"item": item, "qty": int(qty), "total": round(total), "avg_price": round(total / max(1, int(qty)), 1),
                "price_now": self.obs["prices"][item], "price_after": end}

    def plan_crop_mix(self, plots: int | None = None) -> dict[str, Any]:
        n = self.obs["free_plots"] if plots is None else int(plots)
        mix = crop_mix(self.obs, n)
        return {"plots": n, "mix": mix,
                "per_crop": {c: estimate_crop_profit(c, self.obs, k)["expected_profit"] for c, k in mix.items()}}

    def simulate_action(self, plan: dict[str, Any] | None = None, days: int = 5) -> dict[str, Any]:
        days = max(1, min(int(days), 8))
        res = self.env.simulate(plan or {}, days=days,
                                follow_up=lambda o: strategic_plan(o, land=False, animals=False))
        return res


def compact(obj: Any, limit: int = 1800) -> str:
    """JSON-encode a tool result, trimmed so prompts stay small."""
    s = json.dumps(obj, default=str, separators=(",", ":"))
    return s if len(s) <= limit else s[:limit] + "...(truncated)"
