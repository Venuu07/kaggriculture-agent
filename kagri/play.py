"""Play vs the AI: a human farms seat 1, the agent farms seat 2, on one shared market.

API (mounted by kagri/server.py):
    POST /api/play                    start {seed, events, weather, agent, provider}
    POST /api/play/{sid}/day          submit the human's plan; the AI decides; both farms play the day
    GET  /api/play/{sid}/suggest      a sensible plan for the human (the offline strategist's advice)
"""
from __future__ import annotations

import json
import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .agents.strategy import strategic_plan
from .economics import estimate_crop_profit
from .engine import kaggriculture as kg
from .env import FarmEnv
from .evaluate import make_agent
from .llm.providers import provider_ready
from .runner import snapshot

router = APIRouter()
_games: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


class PlayRequest(BaseModel):
    seed: int = 0
    events: bool = True
    weather: str | None = None
    agent: str = "llm_multi"
    provider: str = "offline"


class DayRequest(BaseModel):
    plan: dict[str, Any] = {}


def _states(base: FarmEnv) -> list[dict[str, Any]]:
    return [snapshot(base.view(i).observe()) for i in (0, 1)]


@router.post("/api/play")
def start(req: PlayRequest) -> dict[str, Any]:
    if req.agent not in ("llm_multi", "llm_single", "greedy", "random"):
        raise HTTPException(400, "unknown agent")
    provider, note = req.provider, ""
    if req.agent.startswith("llm") and not provider_ready(provider)[0]:
        note, provider = f"{provider_ready(provider)[1]} - the AI uses the offline reasoner.", "offline"
    try:
        env = FarmEnv(events=req.events, weather=req.weather or None)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e
    env.reset(req.seed)
    ai = make_agent(req.agent, provider)
    ai.begin_episode(req.seed)
    sid = uuid.uuid4().hex[:12]
    with _lock:
        if len(_games) > 30:
            _games.pop(next(iter(_games)))
        _games[sid] = {"env": env, "ai": ai, "lock": threading.Lock(), "history": []}
    return {"sid": sid, "ai_label": ai.label, "note": note, "states": _states(env), "day": env.day,
            "weather": env.today_events, "advice": _advice(env.view(0))}


@router.get("/api/play/{sid}/suggest")
def suggest(sid: str) -> dict[str, Any]:
    g = _get(sid)
    obs = g["env"].view(0).observe()
    return {"plan": strategic_plan(obs, land=True, animals=True)}


@router.post("/api/play/{sid}/day")
def play_day(sid: str, req: DayRequest) -> dict[str, Any]:
    g = _get(sid)
    with g["lock"]:
        base: FarmEnv = g["env"]
        if base.done:
            return {"done": True, "states": _states(base)}
        ai_view = base.view(1)
        ai_obs = ai_view.observe()
        decision = g["ai"].decide(ai_obs, ai_view)
        human = base.view(0)
        _, reward, done, info = human.step(req.plan, rival=decision.plan)
        g["env"] = human
        ai_info = {"day": info["day"], "plan": info["rival"]["plan"], "events": info["events"],
                   "rejected": info["rival"]["rejected"]}
        g["ai"].after_step(ai_info, info["rival"]["reward"])
        ai_record = {"day": info["day"], "trace": decision.trace, "plan": info["rival"]["plan"],
                     "rejected": info["rival"]["rejected"], "reward": info["rival"]["reward"],
                     "tokens": decision.tokens, "latency_s": decision.latency_s,
                     "llm_calls": decision.llm_calls, "fallback": decision.fallback}
        you = {"plan": info["plan"], "rejected": info["rejected"], "reward": reward, "sales": info["sales"]}
        g["history"].append({"day": info["day"], "you": reward, "ai": info["rival"]["reward"]})
        out = {"done": done, "day": human.day, "events": info["events"], "you": you, "ai": ai_record,
               "states": _states(human), "weather": human.today_events,
               "advice": None if done else _advice(human)}
        return json.loads(json.dumps(out, default=str))


def _advice(view: FarmEnv) -> dict[str, Any]:
    """What a beginner needs to choose a plan: crop economics today and what is in the shed."""
    obs = view.observe()
    crops = []
    for c in kg.CROPS:
        est = estimate_crop_profit(c, obs, 1)
        crops.append({"crop": c, "seed": kg.CROPS[c]["seed"], "days": est["days_to_harvest"],
                      "profit_per_plot": est["expected_profit"], "feasible": est["feasible"],
                      "price": obs["prices"][c]})
    animals = [{"animal": a, "cost": kg.ANIMALS[a]["cost"], "product": kg.ANIMALS[a]["product"]} for a in kg.ANIMALS]
    return {"crops": crops, "animals": animals, "cash": obs["cash"], "free_plots": obs["free_plots"],
            "shed": obs["shed"], "next_land_cost": obs["next_land_cost"], "days_left": obs["days_left"],
            "growing": sum(obs["crops_growing"].values()) + sum(obs["animals"].values())}


def _get(sid: str) -> dict[str, Any]:
    g = _games.get(sid)
    if g is None:
        raise HTTPException(404, "game expired - start a new one")
    return g
