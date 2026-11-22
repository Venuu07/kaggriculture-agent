"""Scenario Lab: stress-test the agent with a scripted crisis and compare it with Greedy.

Each scenario is a controlled experiment: fixed weather days, pest days and market shocks, and
no random events. Every agent also plays a calm season on the same farm, so "resilience" is
profit in the crisis divided by profit in calm conditions.

    python -m kagri.scenarios          # precompute every scenario -> results/scenarios.json (~1 min)
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import RESULTS_DIR
from .evaluate import make_agent
from .runner import run_episode

SCENARIOS: dict[str, dict[str, Any]] = {
    "calm": {"title": "Calm season", "blurb": "Sunny all month, no pests, no shocks. The control group.",
             "script": {"base_weather": "sunny"}},
    "drought": {"title": "Drought week", "blurb": "Days 6-13: any plant not watered by nightfall dies. Labour is everything.",
                "script": {"base_weather": "sunny", "weather": {str(d): "drought" for d in range(6, 14)}}},
    "melon_crash": {"title": "Melon market crash", "blurb": "Day 11 and 18: a flood of imported melons sends the price towards $1.",
                    "script": {"base_weather": "sunny", "shocks": {"11": [["MELON", 2.0]], "18": [["MELON", 1.0]]}}},
    "pest_wave": {"title": "Pest wave", "blurb": "Days 8, 14 and 20: pests destroy 30% of unfertilised plants.",
                  "script": {"base_weather": "sunny", "pests": [8, 14, 20], "pest_rate": 0.3}},
    "monsoon": {"title": "Monsoon with fungus", "blurb": "Days 4-16: heavy rain waters everything for free, but fungus hits on days 10 and 15.",
                "script": {"base_weather": "cloudy", "weather": {str(d): "heavy_rain" for d in range(4, 17)},
                           "pests": [10, 15], "pest_rate": 0.25}},
    "demand_boom": {"title": "Festival demand boom", "blurb": "Day 9: a festival empties the market of milk, eggs and strawberries. An opportunity.",
                    "script": {"base_weather": "sunny", "shocks": {"9": [["MILK", -1.0], ["EGG", -1.0], ["STRAWBERRY", -1.0]]}}},
}
AGENTS = ["llm_multi", "greedy"]
router = APIRouter()
_cache: dict[str, Any] = {}


def _event_days(script: dict[str, Any]) -> list[int]:
    days = {int(d) for d in script.get("weather", {})} | set(script.get("pests", [])) | {int(d) for d in script.get("shocks", {})}
    return sorted(days)


def run_one(args: tuple[str, str, int]) -> dict[str, Any]:
    """One agent on one scenario: daily cash, events and the agent's reasoning on event days."""
    scen, agent_key, seed = args
    script = SCENARIOS[scen]["script"]
    agent = make_agent(agent_key, "offline")
    summary = run_episode(agent, seed, None, events=True, scenario=script)
    event_days = set(_event_days(script))
    notes = []
    for r in summary["records"]:
        if r["day"] in event_days or r["events"].get("events"):
            thoughts = [t["text"] for t in r["trace"] if t.get("type") == "thought"]
            notes.append({"day": r["day"], "events": r["events"].get("events", []), "weather": r["events"].get("weather"),
                          "thought": thoughts[-1] if thoughts else "", "plan": r["plan"], "reward": round(r["reward"])})
    return {"scenario": scen, "agent": agent_key, "label": agent.label, "seed": seed,
            "profit": round(summary["profit"]), "daily_profit": [round(c - 3000) for c in summary["daily_cash"]],
            "notes": notes}


def run_scenario(scen: str, seed: int = 0, parallel: bool = False) -> dict[str, Any]:
    jobs = [(s, a, seed) for s in {scen, "calm"} for a in AGENTS]
    if parallel:
        with ProcessPoolExecutor() as ex:
            rows = list(ex.map(run_one, jobs))
    else:
        rows = [run_one(j) for j in jobs]
    calm = {r["agent"]: r["profit"] for r in rows if r["scenario"] == "calm"}
    runs = [r for r in rows if r["scenario"] == scen]
    for r in runs:
        r["calm_profit"] = calm[r["agent"]]
        r["resilience_pct"] = round(100 * r["profit"] / calm[r["agent"]], 1) if calm[r["agent"]] else None
    meta = SCENARIOS[scen]
    return {"scenario": scen, "title": meta["title"], "blurb": meta["blurb"], "seed": seed,
            "event_days": _event_days(meta["script"]), "runs": runs}


class ScenarioRequest(BaseModel):
    scenario: str
    seed: int = 0


@router.get("/api/scenarios")
def list_scenarios() -> dict[str, Any]:
    cached = {}
    path = RESULTS_DIR / "scenarios.json"
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
    return {"scenarios": [{"id": k, "title": v["title"], "blurb": v["blurb"], "event_days": _event_days(v["script"])}
                          for k, v in SCENARIOS.items()], "results": cached}


@router.post("/api/scenarios/run")
def run_api(req: ScenarioRequest) -> dict[str, Any]:
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario; choose from {list(SCENARIOS)}")
    key = f"{req.scenario}:{req.seed}"
    if key not in _cache:
        _cache[key] = run_scenario(req.scenario, req.seed)
    return _cache[key]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    jobs = [(s, ag, a.seed) for s in SCENARIOS for ag in AGENTS]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run_one, jobs))
    calm = {r["agent"]: r["profit"] for r in rows if r["scenario"] == "calm"}
    out: dict[str, Any] = {}
    for s, meta in SCENARIOS.items():
        runs = [r for r in rows if r["scenario"] == s]
        for r in runs:
            r["calm_profit"] = calm[r["agent"]]
            r["resilience_pct"] = round(100 * r["profit"] / calm[r["agent"]], 1) if calm[r["agent"]] else None
        out[s] = {"scenario": s, "title": meta["title"], "blurb": meta["blurb"], "seed": a.seed,
                  "event_days": _event_days(meta["script"]), "runs": runs}
        line = "  ".join(f"{r['agent']}: ${r['profit']:,} ({r['resilience_pct']}% of calm)" for r in runs)
        print(f"{meta['title']:<26} {line}")
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "scenarios.json").write_text(json.dumps(out), encoding="utf-8")


if __name__ == "__main__":
    main()
