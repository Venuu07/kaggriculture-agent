"""The shopkeeper agent: the SAME ReAct core (kagri/agents/core.py) with shop tools and prompt.

Also: a fixed-rule baseline, an offline shopkeeper reasoner (no API key needed), a runner that
logs JSONL in the same format as the farm, and the API routes for the dashboard.

    python -m kagri.shop        # agent vs fixed-rule baseline over 5 seeds, demo runs in runs/
"""
from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from .. import RESULTS_DIR, RUNS_DIR
from ..agents.core import react_loop
from ..llm.providers import LLMError, LLMReply, Provider, get_provider
from .env import DAYS, PRODUCTS, ShopEnv

SYSTEM = """You are the AI manager of a kirana store (an Indian neighbourhood grocery), 30 days, start Rs 10,000.
Every day you set prices and order stock. Orders are paid now and arrive TOMORROW. Score = cash on day 30.
Products (cost -> usual price, shelf life, usual customers/day):
  MILK 22 -> 30, 2 days, 40 | BREAD 25 -> 35, 3 days, 25 | RICE 40 -> 55, no expiry, 30
  ICE_CREAM 30 -> 50, freezer, 10 (x3 in a heatwave) | SWEETS 60 -> 100, 5 days, 6 (x5 at a festival)
Expired stock is thrown away. Higher prices mean fewer customers (each product reacts differently).
Prices must stay within 0.7x-1.5x the usual price. Shelf holds 450 units.
PLAN: {{"order": {{"MILK": 60, ...}}, "price": {{"MILK": 32, ...}}}}

TOOLS:
{tools}
- take_action(args={{"plan": {{...}}}}): commit today's plan (ends your turn).

You work in a loop (ReAct): think, call ONE tool, read its result, repeat; then commit.
Reply with ONE JSON object: {{"thought": "...", "action": "<tool or take_action>", "args": {{...}}}}
You may call at most {max_tools} tools. Test candidate plans with simulate_plan before committing."""


class ShopTools:
    """Tools bound to the live store for one decision."""

    def __init__(self, env: ShopEnv, obs: dict[str, Any]) -> None:
        self.env, self.obs = env, obs
        self.tools = {
            "get_store_state": ("Cash, stock per product with days until expiry, prices, recent sales.", "{}"),
            "get_demand_forecast": ("Today's events and a 3-day forecast (weather, festival).", "{}"),
            "estimate_demand": ("Expected customers for a product today at a given price.", '{"product": "MILK", "price": 30}'),
            "suggest_plan": ("A forecast-based plan: order to cover expected demand, mark down stock about to expire.", "{}"),
            "simulate_plan": ("Look-ahead: play a candidate plan on a COPY of the store for N days; returns the change in "
                              "cash + stock value.", '{"plan": {...}, "days": 4}'),
        }

    def describe(self, allowed: list[str] | None = None) -> str:
        return "\n".join(f"- {n}(args={a}): {d}" for n, (d, a) in self.tools.items() if allowed is None or n in allowed)

    def call(self, name: str, args: Any) -> dict[str, Any]:
        args = args if isinstance(args, dict) else {}
        try:
            if name == "get_store_state":
                o = self.obs
                return {"day": o["day"], "days_left": o["days_left"], "cash": o["cash"], "shelf_space_left": o["shelf_space_left"],
                        "products": {p: {k: v for k, v in d.items() if k in ("stock", "batches", "on_order", "price", "sold_last_days")}
                                     for p, d in o["products"].items()}}
            if name == "get_demand_forecast":
                return {"today": self.obs["today"], "forecast": self.obs["forecast"]}
            if name == "estimate_demand":
                p = str(args.get("product", "")).upper()
                if p not in PRODUCTS:
                    return {"error": f"unknown product; choose from {list(PRODUCTS)}"}
                price = float(args.get("price", PRODUCTS[p]["price"]))
                n = expected_demand(self.obs, p, self.obs["day"], price, today=True)
                return {"product": p, "price": price, "expected_customers": round(n, 1), "expected_revenue": round(n * price)}
            if name == "suggest_plan":
                return {"plan": forecast_plan(self.obs)}
            if name == "simulate_plan":
                plan = args.get("plan") or {}
                days = max(1, min(int(args.get("days", 4)), 6))
                return self.env.simulate(plan, days, follow_up=forecast_plan)
            return {"error": f"unknown tool '{name}'"}
        except Exception as e:  # a tool must never crash the agent
            return {"error": f"{name} failed: {type(e).__name__}: {e}"}


def expected_demand(obs: dict[str, Any], p: str, day: int, price: float, today: bool = False) -> float:
    """Demand the shopkeeper can expect, using only what it can see (today's events, the forecast)."""
    meta = PRODUCTS[p]
    f = 1.3 if day % 7 in (5, 6) else 1.0
    if today:
        info = obs["today"]
        weather, festival = info["weather"], any("Festival" in e for e in info["events"])
        promo = any("promotion" in e and p.lower().replace("_", " ") in e for e in info["events"])
    else:
        fc = next((x for x in obs["forecast"] if x["day"] == day), {"weather": "normal", "festival": False})
        weather, festival, promo = fc["weather"], fc["festival"], False
    if weather == "heatwave":
        f *= 3.0 if p == "ICE_CREAM" else (1.1 if p == "MILK" else 1.0)
    elif weather == "rain":
        f *= 0.8
    if festival:
        f *= 5.0 if p == "SWEETS" else (1.5 if p == "MILK" else 1.0)
    if promo:
        f *= 0.7
    return meta["demand"] * f * (price / meta["price"]) ** (-meta["elasticity"])


def forecast_plan(obs: dict[str, Any], order_mult: float = 1.0, price_mult: float = 1.0) -> dict[str, Any]:
    """Order to cover forecast demand for the shelf life; mark down stock that is about to expire."""
    plan: dict[str, Any] = {"order": {}, "price": {}}
    day = obs["day"]
    for p, meta in PRODUCTS.items():
        info = obs["products"][p]
        base = meta["price"]
        price = base * price_mult
        today = expected_demand(obs, p, day, price, today=True)
        expiring = sum(b["qty"] for b in info["batches"] if b["days_left"] <= 1)
        if expiring > today * 1.1:
            price = base * 0.8
        elif info["stock"] < today * 0.7:
            price = base * 1.15
        if obs["today"]["weather"] == "heatwave" and p == "ICE_CREAM":
            price = max(price, base * 1.2)
        plan["price"][p] = round(min(1.5 * base, max(0.7 * base, price)))
        sell_today = min(info["stock"], expected_demand(obs, p, day, plan["price"][p], today=True))
        cover = 2 if meta["life"] >= 3 else 1
        need = sum(expected_demand(obs, p, d, base) for d in range(day + 1, min(DAYS, day + 1 + cover)))
        usable = info["stock"] - sell_today - sum(b["qty"] for b in info["batches"] if b["days_left"] <= 1)
        q = max(0, need - max(0, usable) - info["on_order"]) * order_mult
        if obs["days_left"] <= 1:
            q = 0
        if q >= 1:
            plan["order"][p] = int(math.ceil(q))
    return plan


def fixed_plan(obs: dict[str, Any]) -> dict[str, Any]:
    """Baseline: restock what usually sells, at the usual price, every day."""
    if obs["days_left"] <= 1:
        return {"order": {}, "price": {p: m["price"] for p, m in PRODUCTS.items()}}
    return {"order": {p: max(0, m["demand"] - obs["products"][p]["stock"] // 2) for p, m in PRODUCTS.items()},
            "price": {p: m["price"] for p, m in PRODUCTS.items()}}


class ShopOfflineReasoner(Provider):
    """Rule-based shopkeeper speaking the same JSON protocol (no LLM): forecast, then compare
    candidate plans with simulate_plan, then commit the best."""

    name = "offline"

    def __init__(self) -> None:
        super().__init__()
        self.min_interval = 0.0

    def respond(self, system: str, messages: list[dict[str, str]], ctx: dict[str, Any] | None = None) -> LLMReply:
        ctx = ctx or {}
        obs, steps = ctx["obs"], ctx["steps"]
        cands = [("balanced", forecast_plan(obs)), ("stock up", forecast_plan(obs, 1.25)),
                 ("lean, higher prices", forecast_plan(obs, 0.8, 1.08))]
        say = lambda t, a, g=None: LLMReply(json.dumps({"thought": t, "action": a, "args": g or {}}))  # noqa: E731
        if not steps:
            ev = [e.rstrip(".") for e in obs["today"]["events"]] or ["a normal day"]
            return say(f"Day {obs['day']}, Rs {obs['cash']:,.0f} in the till. Today: {'; '.join(ev)}. Checking the forecast.",
                       "get_demand_forecast")
        sims = [s for s in steps if s["name"] == "simulate_plan"]
        if len(sims) < len(cands):
            name, plan = cands[len(sims)]
            lead = ""
            if not sims:
                fc = steps[0]["result"].get("forecast", [])
                hot = [f["day"] for f in fc if f["weather"] == "heatwave"]
                fest = [f["day"] for f in fc if f["festival"]]
                lead = (f"Heatwave expected on day {hot[0]}: stock ice cream. " if hot else "") + \
                       (f"Festival on day {fest[0]}: stock sweets and milk. " if fest else "")
            return say(f"{lead}Simulating '{name}' 4 days ahead.", "simulate_plan", {"plan": plan, "days": 4})
        scored = [(s["result"].get("worth_change", -1e9), cands[i][0], cands[i][1]) for i, s in enumerate(sims)]
        v, name, plan = max(scored, key=lambda t: t[0])
        compare = ", ".join(f"'{n}' {x:+,}" for x, n, _ in scored)
        return say(f"Look-ahead: {compare}. Going with '{name}'.", "take_action", {"plan": plan})


class ShopAgent:
    """The shopkeeper. `provider` = offline | gemini | groq | openai | claude."""

    def __init__(self, provider: str = "offline", test_before_act: bool = False) -> None:
        self.provider: Provider = ShopOfflineReasoner() if provider == "offline" else get_provider(provider)
        self.name, self.label = "shop_agent", f"AI shopkeeper ({self.provider.name})"
        self.test_before_act = test_before_act

    def decide(self, obs: dict[str, Any], env: ShopEnv) -> dict[str, Any]:
        stats = {"tokens": 0, "calls": 0, "latency": 0.0}

        def account(reply: Any) -> None:
            stats["tokens"] += reply.tokens
            stats["latency"] += reply.latency_s
            stats["calls"] += 0 if self.provider.name == "offline" else 1

        tools = ShopTools(env, obs)
        trace: list[dict[str, Any]] = []
        try:
            plan = react_loop(provider=self.provider, role="shopkeeper", toolbox=tools, trace=trace, account=account,
                              system=SYSTEM.format(tools=tools.describe(), max_tools=4),
                              first_message=f"TODAY: {json.dumps({k: obs[k] for k in ('day', 'days_left', 'cash', 'today')})}\n"
                                            "Decide today's plan.",
                              ctx={"obs": obs, "env": env}, max_tools=4, max_retries=2,
                              test_before_act=self.test_before_act, simulate_tool="simulate_plan")
        except LLMError as e:
            trace.append({"type": "error", "agent": "system", "text": str(e)})
            plan = None
        fallback = plan is None
        if fallback:
            plan = forecast_plan(obs)
            trace.append({"type": "fallback", "agent": "system", "text": "LLM reply unusable - using the forecast plan."})
        return {"plan": plan, "trace": trace, "fallback": fallback, **stats}


def run_shop(kind: str, seed: int, log: Path | None = None, provider: str = "offline") -> dict[str, Any]:
    """Play one store season with the agent ('agent') or the fixed-rule baseline ('baseline')."""
    env = ShopEnv()
    obs = env.reset(seed)
    agent = ShopAgent(provider) if kind == "agent" else None
    label = agent.label if agent else "Fixed restock rule"
    days, f = [], None
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        f = log.open("w", encoding="utf-8")
        f.write(json.dumps({"type": "header", "world": "shop", "agent": kind, "label": label, "seed": seed}) + "\n")
    while not env.done:
        before = obs
        t0 = time.perf_counter()
        d = agent.decide(obs, env) if agent else {"plan": fixed_plan(obs), "trace": [], "fallback": False,
                                                    "tokens": 0, "calls": 0, "latency": 0.0}
        obs, reward, done, info = env.step(d["plan"])
        rec = {"type": "day", "day": info["day"], "before": before, "trace": d["trace"], "plan": info["plan"],
               "rejected": info["rejected"], "reward": round(reward), "cash": round(env.cash), "sold": info["sold"],
               "demand": info["demand"], "wasted": info["wasted"], "revenue": info["revenue"], "events": info["events"],
               "tokens": d["tokens"], "llm_calls": d["calls"], "latency_s": round(d["latency"] or time.perf_counter() - t0, 3),
               "fallback": d["fallback"]}
        days.append(rec)
        if f:
            f.write(json.dumps(rec, default=str) + "\n")
    wasted = sum(sum(r["wasted"].values()) for r in days)
    lost = sum(max(0, r["demand"][p] - r["sold"][p]) for r in days for p in PRODUCTS)
    summary = {"type": "summary", "agent": kind, "label": label, "seed": seed, "profit": round(env.profit),
               "units_wasted": wasted, "customers_lost": lost, "final": obs}
    if f:
        f.write(json.dumps(summary, default=str) + "\n")
        f.close()
    return summary


def _job(args: tuple[str, int]) -> dict[str, Any]:
    kind, seed = args
    log = RUNS_DIR / f"shop_{kind}_seed0.jsonl" if seed == 0 else None
    s = run_shop(kind, seed, log)
    return {k: s[k] for k in ("agent", "label", "seed", "profit", "units_wasted", "customers_lost")}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5)
    a = ap.parse_args(argv)
    jobs = [(k, s) for k in ("agent", "baseline") for s in range(a.seeds)]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_job, jobs))
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "shop.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for k in ("agent", "baseline"):
        r = [x for x in rows if x["agent"] == k]
        print(f"{r[0]['label']:<30} profit Rs {sum(x['profit'] for x in r) / len(r):>9,.0f}  "
              f"wasted {sum(x['units_wasted'] for x in r) / len(r):>6.0f}  lost customers {sum(x['customers_lost'] for x in r) / len(r):>6.0f}")


router = APIRouter()


@router.get("/api/shop")
def shop_api() -> dict[str, Any]:
    out: dict[str, Any] = {"results": [], "runs": {}}
    res = RESULTS_DIR / "shop.json"
    if res.exists():
        out["results"] = json.loads(res.read_text(encoding="utf-8"))
    for kind in ("agent", "baseline"):
        path = RUNS_DIR / f"shop_{kind}_seed0.jsonl"
        if path.exists():
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            out["runs"][kind] = {"header": rows[0], "days": [r for r in rows if r.get("type") == "day"],
                                 "summary": rows[-1] if rows[-1].get("type") == "summary" else {}}
    if not out["runs"]:
        raise HTTPException(404, "no shop runs yet; run python -m kagri.shop")
    return out


if __name__ == "__main__":
    main()
