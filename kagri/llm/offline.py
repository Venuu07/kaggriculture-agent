"""Offline reasoner: a deterministic stand-in for an LLM, used when there is no API key or no internet.

It is NOT a language model. It speaks the same JSON protocol as the real providers
({"thought", "action", "args"}), calls the same tools through the same ReAct loop, and
writes rule-based "thoughts" that quote the real tool results. This keeps the demo, the
logs and the evaluation pipeline working with zero network access. Everything it produces
is labelled 'offline' in the UI and in results.csv.
"""
from __future__ import annotations

import json
from typing import Any

from ..agents.strategy import MAX_HANDS, fertiliser_targets, hands_needed, sell_orders, strategic_plan
from ..engine import kaggriculture as kg
from .providers import LLMReply, Provider


def _say(thought: str, action: str, args: dict[str, Any] | None = None) -> LLMReply:
    return LLMReply(json.dumps({"thought": thought, "action": action, "args": args or {}}))


def _brief(plan: dict[str, Any]) -> str:
    parts = []
    if plan.get("plant"):
        parts.append("plant " + ", ".join(f"{n} {c.lower()}" for c, n in plan["plant"].items()))
    if plan.get("buy_land"):
        parts.append("buy land")
    if plan.get("buy_animals"):
        parts.append("buy " + ", ".join(f"{n} {a.lower()}" for a, n in plan["buy_animals"].items()))
    if plan.get("sell"):
        parts.append("sell " + ", ".join(f"{q} {i.lower()}" for i, q in plan["sell"].items()))
    if plan.get("hands"):
        parts.append(f"{plan['hands']} hands")
    return "; ".join(parts) or "maintenance only"


def _weather_adjust(plan: dict[str, Any], obs: dict[str, Any]) -> str:
    """Tweak labour for today's weather; returns an explanation."""
    w = (obs.get("weather") or {}).get("weather")
    if w == "drought":
        plan["hands"] = min(MAX_HANDS, plan.get("hands", 0) + 1)
        return "Drought today, so I add a hand to make sure every plant is watered."
    if w == "heavy_rain" and plan.get("hands", 0) > 1:
        plan["hands"] -= 1
        return "Heavy rain waters everything, so I can save one hand."
    return ""


class OfflineReasoner(Provider):
    """Rule-based reasoner that drives the ReAct loop without any network calls."""

    name = "offline"

    def __init__(self) -> None:
        super().__init__()
        self.min_interval = 0.0

    @property
    def model(self) -> str:
        return "offline-rule-reasoner"

    def respond(self, system: str, messages: list[dict[str, str]], ctx: dict[str, Any] | None = None) -> LLMReply:
        ctx = ctx or {}
        role = ctx.get("role", "single")
        handler = getattr(self, f"_{role}", self._single)
        return handler(ctx)

    # --------------------------------------------------------------- roles
    def _candidates(self, ctx: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        obs, params = ctx["obs"], ctx.get("params") or {}
        land_ok = params.get("allow_land", True)
        animals_ok = params.get("allow_animals", True)
        cands = [("expand", strategic_plan(obs, params, land=land_ok, animals=animals_ok)),
                 ("no land", strategic_plan(obs, params, land=False, animals=animals_ok)),
                 ("crops only", strategic_plan(obs, params, land=False, animals=False))]
        if params.get("no_lookahead"):
            cands = cands[:1]
        uniq: list[tuple[str, dict[str, Any]]] = []
        for name, plan in cands:
            if all(plan != p for _, p in uniq):
                uniq.append((name, plan))
        return uniq

    def _single(self, ctx: dict[str, Any]) -> LLMReply:
        obs, steps = ctx["obs"], ctx["steps"]
        n = len(steps)
        cands = self._candidates(ctx)[:2]
        if (ctx.get("params") or {}).get("no_lookahead") and n == 0:
            plan = dict(cands[0][1])
            note = _weather_adjust(plan, obs)
            return _say(f"Day {obs['day']}: no look-ahead (ablation). Taking the default plan: {_brief(plan)}. {note}".strip(),
                        "take_action", {"plan": plan})
        if n == 0:
            return _say(f"Day {obs['day']}: ${obs['cash']:.0f} cash, {obs['free_plots']} free plots, "
                        f"{sum(obs['crops_growing'].values())} plants growing. First, the weather.",
                        "get_weather_forecast")
        if n == 1:
            w = steps[0]["result"]["today"].get("weather")
            return _say(f"Weather today is {w}. Next I want a glut-aware crop mix for my free plots.",
                        "plan_crop_mix", {"plots": obs["free_plots"]})
        sims = [s for s in steps if s["name"] == "simulate_action"]
        if len(sims) < len(cands) and n < 4:
            name, plan = cands[len(sims)]
            mix = steps[1]["result"].get("mix", {})
            lead = f"Suggested mix {mix}. " if len(sims) == 0 else ""
            days = int((ctx.get("params") or {}).get("lookahead_days", 5))
            return _say(f"{lead}Simulating candidate '{name}' ({_brief(plan)}) {days} days ahead.",
                        "simulate_action", {"plan": plan, "days": days})
        scored = [(s["result"].get("net_worth_change", -1e9), cands[i][0], cands[i][1]) for i, s in enumerate(sims)]
        best = max(scored, key=lambda t: t[0]) if scored else (0, cands[0][0], cands[0][1])
        plan = dict(best[2])
        note = _weather_adjust(plan, obs)
        compare = ", ".join(f"'{nm}' {v:+.0f}" for v, nm, _ in scored)
        return _say(f"Look-ahead net worth: {compare}. I pick '{best[1]}': {_brief(plan)}. {note}".strip(),
                    "take_action", {"plan": plan})

    def _planner(self, ctx: dict[str, Any]) -> LLMReply:
        obs, steps = ctx["obs"], ctx["steps"]
        cands = self._candidates(ctx)
        if len(cands) == 1 and not steps:
            part = {k: cands[0][1][k] for k in ("plant", "buy_land", "buy_animals") if cands[0][1].get(k)}
            return _say(f"No free plots and no affordable investment today; nothing to choose between. "
                        f"Proposing {_brief(part)}.", "take_action", {"plan": part})
        if not steps:
            return _say(f"{obs['free_plots']} free plots, next land costs {obs['next_land_cost']}. "
                        "Start with a glut-aware crop mix.", "plan_crop_mix", {"plots": obs["free_plots"]})
        sims = [s for s in steps if s["name"] == "simulate_action"]
        if len(sims) < len(cands) and len(steps) < 4:
            name, plan = cands[len(sims)]
            part = {k: plan[k] for k in ("plant", "buy_land", "buy_animals") if plan.get(k)}
            return _say(f"Test land-use option '{name}': {_brief(part)} (8 days ahead, investments pay back slowly).",
                        "simulate_action", {"plan": plan, "days": 8})
        scored = [(s["result"].get("net_worth_change", -1e9), cands[i][0], cands[i][1]) for i, s in enumerate(sims)]
        v, name, plan = max(scored, key=lambda t: t[0]) if scored else (0, cands[0][0], cands[0][1])
        part = {k: plan[k] for k in ("plant", "buy_land", "buy_animals") if plan.get(k)}
        compare = ", ".join(f"'{nm}' {val:+.0f}" for val, nm, _ in scored)
        return _say(f"Simulated: {compare}. Proposing '{name}'.", "take_action", {"plan": part})

    def _market(self, ctx: dict[str, Any]) -> LLMReply:
        obs, steps = ctx["obs"], ctx["steps"]
        stock = {k: v for k, v in obs["shed"].items() if k in kg.PRODUCTS}
        if not stock:
            return _say("The shed is empty, nothing to sell today.", "take_action", {"plan": {"sell": {}}})
        if not steps:
            return _say(f"Shed holds {stock}. Checking prices and town demand.", "get_market_prices", {"history_days": 5})
        sell = sell_orders(obs, (ctx.get("params") or {}).get("sell_floor", 0.65))
        top = max(stock, key=lambda k: stock[k] * obs["prices"][k])
        if len(steps) == 1:
            return _say(f"{top} is my most valuable stock; how far would selling all {stock[top]} push its price?",
                        "estimate_sale", {"item": top, "qty": stock[top]})
        est = steps[1]["result"]
        held = {k: stock[k] - sell.get(k, 0) for k in stock if stock[k] - sell.get(k, 0) > 0}
        why = (f"Selling all {top} would drop its price ${est.get('price_now')}->${est.get('price_after')}. "
               if "price_after" in est else "")
        tail = f"Holding {held} for better prices." if held else "Selling everything."
        if obs["days_left"] <= 1:
            tail = "Last day: sell everything, unsold stock is worth nothing."
        return _say(f"{why}{tail}", "take_action", {"plan": {"sell": sell}})

    def _agronomist(self, ctx: dict[str, Any]) -> LLMReply:
        obs, steps = ctx["obs"], ctx["steps"]
        if not steps:
            return _say("Check today's weather and the forecast before setting labour.", "get_weather_forecast")
        params = ctx.get("params") or {}
        plan = {"fertilise": fertiliser_targets(obs),
                "hands": min(MAX_HANDS, hands_needed(obs, obs["free_plots"]) + int(params.get("hands_bonus", 0)))}
        note = _weather_adjust(plan, obs)
        fc = [f["weather"] for f in steps[0]["result"].get("forecast", [])]
        return _say(f"Forecast {fc}. {note} Fertilise {plan['fertilise'] or 'nothing'}; {plan['hands']} hands "
                    "for the watering load.".strip(), "take_action", {"plan": plan})

    def _manager(self, ctx: dict[str, Any]) -> LLMReply:
        obs, steps, props = ctx["obs"], ctx["steps"], ctx.get("proposals") or {}
        merged: dict[str, Any] = {}
        for role in ("planner", "market", "agronomist"):
            merged.update(props.get(role) or {})
        new_work = sum((merged.get("plant") or {}).values()) + sum((merged.get("buy_animals") or {}).values())
        params = ctx.get("params") or {}
        need = min(MAX_HANDS, hands_needed(obs, new_work) + int(params.get("hands_bonus", 0))
                   + (1 if (obs.get("weather") or {}).get("weather") == "drought" else 0))
        conflict = ""
        if merged.get("hands", 0) < need:
            conflict = f" Conflict: {merged.get('hands', 0)} hands cannot tend {new_work} new tiles; raising to {need}."
            merged["hands"] = need
        lean = {k: v for k, v in merged.items() if k not in ("buy_land", "buy_animals")}
        if not steps and not params.get("no_lookahead"):
            return _say(f"Planner: {_brief(props.get('planner') or {})}. Market: {_brief(props.get('market') or {})}. "
                        f"Agronomist: {_brief(props.get('agronomist') or {})}.{conflict} Check the merged plan.",
                        "simulate_action", {"plan": merged, "days": 8})
        if (ctx.get("params") or {}).get("no_lookahead"):
            return _say(f"Merged plan approved without look-ahead (ablation).{conflict}", "take_action", {"plan": merged})
        if len(steps) == 1 and lean != merged:
            return _say("Sanity check: the same plan without new investments.", "simulate_action",
                        {"plan": lean, "days": 8})
        v_merged = steps[0]["result"].get("net_worth_change", 0)
        if len(steps) > 1 and steps[1]["result"].get("net_worth_change", -1e9) > v_merged:
            return _say(f"Leaner plan wins ({steps[1]['result']['net_worth_change']:+.0f} vs {v_merged:+.0f}); "
                        "postponing investments.", "take_action", {"plan": lean})
        return _say(f"Merged plan simulates {v_merged:+.0f} net worth; approving it.", "take_action", {"plan": merged})

    def _reflect(self, ctx: dict[str, Any]) -> LLMReply:
        """Evidence-based lessons plus numeric adjustments the offline planner can apply."""
        ev, old = ctx["evidence"], dict(ctx.get("params") or {})
        lessons: list[str] = []
        params: dict[str, float] = {}
        for item in ("MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT"):
            s = ev["sales"].get(item)
            if s and s["units"] >= 20 and s["avg_price"] < 0.6 * s["base"]:
                bias = round(old.get(f"bias_{item}", 1.0) * 0.85, 3)
                params[f"bias_{item}"] = bias
                lessons.append(f"{item} averaged ${s['avg_price']} vs base ${s['base']}: plant fewer {item.lower()} "
                               "to avoid a glut.")
        if ev["avg_cash_first_10_days"] > 2500:
            params["animal_share"] = min(0.6, old.get("animal_share", 0.35) + 0.1)
            lessons.append("Cash sat idle early in the season; invest sooner in animals (they also give fertiliser).")
        if ev.get("animals_bought_after_day_15", 0) > 0:
            params["animal_min_days"] = old.get("animal_min_days", 12) + 3
            lessons.append(f"Bought {ev['animals_bought_after_day_15']} animals after day 15; they could not pay back. "
                           "Stop buying animals earlier.")
        unsold = {k: v for k, v in ev.get("final_unsold_stock", {}).items() if k in kg.PRODUCTS}
        if unsold:
            lessons.append(f"Season ended with unsold {unsold}; sell down stock over the last three days.")
        fert = ev["sales"].get("FERTILIZER")
        if fert and fert["avg_price"] < 50:
            params["sell_floor"] = min(0.8, old.get("sell_floor", 0.65) + 0.05)
            lessons.append("Fertiliser sold cheaply; hold more stock back and spread sales over more days.")
        if not lessons:
            lessons.append(f"Season made ${ev['profit']}; the plan worked, keep the same balance of crops and animals.")
        return LLMReply(json.dumps({"lessons": lessons, "params": params}))
