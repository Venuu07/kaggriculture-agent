"""Run one episode with any agent and log every day to JSONL (used by evaluation, UI and replay)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .agents.base import Agent
from .env import FarmEnv


def snapshot(obs: dict[str, Any]) -> dict[str, Any]:
    """The part of an observation the UI needs to redraw the farm."""
    keys = ["day", "cash", "profit", "opponent_cash", "grid", "prices", "shed", "weather", "forecast",
            "crops_growing", "animals", "free_plots", "weeds", "land_quadrants", "town_shops", "plots"]
    return {k: obs.get(k) for k in keys}


def run_episode(agent: Agent, seed: int = 0, log_path: Path | None = None, events: bool | None = None,
                on_day: Any = None, meta: dict[str, Any] | None = None, weather: str | None = None,
                scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    """Play a full season. Returns a summary; writes one JSON line per day if `log_path` is set."""
    env = FarmEnv(events=events, weather=weather, scenario=scenario)
    obs = env.reset(seed)
    agent.begin_episode(seed)
    records: list[dict[str, Any]] = []
    totals = {"tokens": 0, "cost_usd": 0.0, "latency_s": 0.0, "llm_calls": 0, "fallbacks": 0}
    f = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        f = log_path.open("w", encoding="utf-8")
        header = {"type": "header", "agent": agent.name, "label": agent.label, "seed": seed,
                  "events": env.events_on, "starting_cash": env.starting_money,
                  "weather_source": env.real_weather["label"] if env.real_weather else "simulated", **(meta or {})}
        f.write(json.dumps(header) + "\n")
    done = False
    while not done:
        before = snapshot(obs)
        t0 = time.perf_counter()
        decision = agent.decide(obs, env)
        latency = decision.latency_s or (time.perf_counter() - t0)
        obs, reward, done, info = env.step(decision.plan)
        agent.after_step(info, reward)
        rec = {"type": "day", "day": info["day"], "before": before, "trace": decision.trace,
               "plan_requested": decision.plan, "plan": info["plan"], "rejected": info["rejected"],
               "events": info["events"], "sales": info["sales"], "reward": reward, "cash": env.cash,
               "profit": env.profit, "tokens": decision.tokens, "cost_usd": decision.cost_usd,
               "latency_s": round(latency, 3), "llm_calls": decision.llm_calls, "fallback": decision.fallback}
        records.append(rec)
        totals["tokens"] += decision.tokens
        totals["cost_usd"] += decision.cost_usd
        totals["latency_s"] += latency
        totals["llm_calls"] += decision.llm_calls
        totals["fallbacks"] += int(decision.fallback)
        if f:
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
        if on_day:
            on_day(rec, obs)
    summary = {"agent": agent.name, "label": agent.label, "seed": seed, "final_cash": env.cash,
               "profit": env.profit, "opponent_cash": obs["opponent_cash"], "days": len(records),
               "daily_cash": [r["cash"] for r in records], "records": records, "final": snapshot(obs), **totals}
    if f:
        f.write(json.dumps({"type": "summary", **{k: v for k, v in summary.items() if k != "records"}}) + "\n")
        f.close()
    agent.end_episode(summary)
    return summary


def load_run(path: Path) -> dict[str, Any]:
    """Read a JSONL run log back into {header, days, summary}."""
    header: dict[str, Any] = {}
    days: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("type") == "header":
                header = rec
            elif rec.get("type") == "day":
                days.append(rec)
            elif rec.get("type") == "summary":
                summary = rec
    return {"header": header, "days": days, "summary": summary}
