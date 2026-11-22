"""Web API + static UI server.

    python -m kagri.serve           # demo: serves the built React app and the API on http://localhost:8000

Endpoints (all JSON):
    GET  /api/health                      server is up
    GET  /api/providers                   which LLM providers have a key
    GET  /api/runs                        recorded runs in runs/ (for replay)
    GET  /api/runs/{name}                 one recorded run (header, days, summary)
    GET  /api/results                     evaluation tables from results/
    GET  /api/memory                      long-term lessons from memory/
    POST /api/live                        start a live season {agent, provider, seed, events}
    POST /api/live/{sid}/step             play one day, returns the day record
"""
from __future__ import annotations

import csv
import json
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import MEMORY_DIR, RESULTS_DIR, ROOT, RUNS_DIR
from .evaluate import make_agent
from .env import FarmEnv
from .llm.providers import provider_ready
from .play import router as play_router
from .runner import load_run, snapshot

WEB_DIST = ROOT / "web" / "dist"
PROVIDERS = ["offline", "gemini", "groq", "openai", "claude"]
AGENTS = {"random": "Random", "greedy": "Greedy heuristic", "llm_single": "LLM single-agent",
          "llm_multi": "LLM multi-agent"}

app = FastAPI(title="Kaggriculture Agent API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(play_router)

_sessions: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/api/providers")
def providers() -> list[dict[str, Any]]:
    out = []
    for p in PROVIDERS:
        ok, why = provider_ready(p)
        out.append({"name": p, "ready": ok, "detail": why})
    return out


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    out = []
    for path in sorted(RUNS_DIR.glob("*.jsonl")):
        header, summary = _header_and_summary(path)
        if not header:
            continue
        out.append({"name": path.stem, "label": header.get("label"), "agent": header.get("agent"),
                    "provider": header.get("provider", "-"), "seed": header.get("seed"),
                    "events": header.get("events"), "profit": summary.get("profit"),
                    "recorded": path.stem.startswith("recorded_")})
    # Real-LLM recordings first, then the multi-agent demo.
    out.sort(key=lambda r: (not r["recorded"], r["agent"] != "llm_multi", r["name"]))
    return out


@app.get("/api/runs/{name}")
def run(name: str) -> dict[str, Any]:
    path = RUNS_DIR / f"{Path(name).name}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"run {name} not found")
    return load_run(path)


@app.get("/api/results")
def results() -> dict[str, Any]:
    def read(name: str) -> list[dict[str, Any]]:
        p = RESULTS_DIR / name
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            return [_coerce(r) for r in csv.DictReader(f)]

    charts = sorted(p.name for p in RESULTS_DIR.glob("*.png"))
    return {"summary": read("summary.csv"), "rows": read("results.csv"), "reflection": read("reflection.csv"),
            "charts": charts}


@app.get("/api/research")
def research() -> dict[str, Any]:
    """Ablation study and Arena tournament results."""
    def read(name: str) -> list[dict[str, Any]]:
        p = RESULTS_DIR / name
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            return [_coerce(r) for r in csv.DictReader(f)]

    return {"ablation": read("ablation.csv"), "arena": read("arena_ratings.csv"),
            "matrix": read("arena_matrix.csv"), "reflection": read("reflection_verified.csv")}


@app.get("/api/real-llm")
def real_llm() -> list[dict[str, Any]]:
    """Summaries of recorded real-LLM seasons next to same-seed baselines and offline-reasoner runs."""
    out: list[dict[str, Any]] = []
    paths = sorted(RUNS_DIR.glob("recorded_*.jsonl")) + sorted(RUNS_DIR.glob("demo_*.jsonl"))
    for path in paths:
        try:
            run = load_run(path)
        except (OSError, json.JSONDecodeError):
            continue
        h, days, s = run["header"], run["days"], run["summary"]
        if not s or not days or h.get("seed") != 0 or h.get("weather_source", "simulated") != "simulated":
            continue
        tools = [sum(1 for t in d["trace"] if t.get("type") == "tool") for d in days]
        sims = sum(1 for d in days for t in d["trace"] if t.get("type") == "tool" and t.get("name") == "simulate_action")
        guards = sum(1 for d in days for t in d["trace"] if t.get("type") == "guardrail")
        out.append({"name": path.stem, "label": h.get("label"), "agent": h.get("agent"),
                    "provider": h.get("provider", "-"), "model": h.get("model"), "real": path.stem.startswith("recorded_"),
                    "profit": s.get("profit"), "llm_calls": s.get("llm_calls", 0), "tokens": s.get("tokens", 0),
                    "cost_usd": round(s.get("cost_usd", 0.0), 4), "fallback_days": s.get("fallbacks", 0),
                    "tool_calls": sum(tools), "days_with_tools": sum(1 for t in tools if t), "simulations": sims,
                    "guardrails": guards, "minutes": round(s.get("latency_s", 0.0) / 60, 1)})
    out.sort(key=lambda r: -(r["profit"] or 0))
    return out


@app.get("/api/arena/matches")
def arena_matches() -> list[str]:
    return sorted(p.stem for p in RUNS_DIR.glob("arena_*.jsonl"))


@app.get("/api/arena/matches/{name}")
def arena_match(name: str) -> dict[str, Any]:
    path = RUNS_DIR / f"{Path(name).name}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"match {name} not found")
    out: dict[str, Any] = {"header": {}, "days": [], "summary": {}}
    with path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            kind = rec.get("type")
            if kind == "arena_header":
                out["header"] = rec
            elif kind == "arena_day":
                out["days"].append(rec)
            elif kind == "arena_summary":
                out["summary"] = rec
    return out


@app.get("/api/memory")
def memory() -> list[dict[str, Any]]:
    out = []
    for p in sorted(MEMORY_DIR.glob("lessons_*.json")):
        try:
            out.append({"name": p.stem.replace("lessons_", ""), "entries": json.loads(p.read_text(encoding="utf-8"))})
        except (OSError, json.JSONDecodeError):
            continue
    return out


class LiveRequest(BaseModel):
    agent: str = "llm_multi"
    provider: str = "offline"
    seed: int = 0
    events: bool = True
    weather: str | None = None


@app.get("/api/weather")
def weather_seasons() -> list[dict[str, Any]]:
    """Cached real-weather seasons (fetched with python -m kagri.realweather)."""
    from .realweather import cached_seasons
    return cached_seasons()


@app.post("/api/live")
def live_start(req: LiveRequest) -> dict[str, Any]:
    if req.agent not in AGENTS:
        raise HTTPException(400, f"agent must be one of {list(AGENTS)}")
    provider = req.provider if req.provider in PROVIDERS else "offline"
    note = ""
    if req.agent.startswith("llm"):
        ok, why = provider_ready(provider)
        if not ok:
            note = f"{why} - switched to the offline reasoner."
            provider = "offline"
    agent = make_agent(req.agent, provider)
    try:
        env = FarmEnv(events=req.events, weather=req.weather or None)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e
    obs = env.reset(req.seed)
    agent.begin_episode(req.seed)
    sid = uuid.uuid4().hex[:12]
    header = {"type": "header", "agent": agent.name, "label": agent.label, "seed": req.seed,
              "events": env.events_on, "starting_cash": env.starting_money, "provider": provider, "live": True,
              "weather_source": env.real_weather["label"] if env.real_weather else "simulated"}
    with _lock:
        if len(_sessions) > 20:
            _sessions.pop(next(iter(_sessions)))
        _sessions[sid] = {"env": env, "agent": agent, "obs": obs, "header": header, "lock": threading.Lock()}
    return {"sid": sid, "header": header, "state": snapshot(obs), "note": note}


@app.post("/api/live/{sid}/step")
def live_step(sid: str) -> dict[str, Any]:
    s = _sessions.get(sid)
    if s is None:
        raise HTTPException(404, "live session expired - start a new one")
    with s["lock"]:
        env, agent, obs = s["env"], s["agent"], s["obs"]
        if env.done:
            return {"done": True, "record": None, "state": snapshot(obs)}
        before = snapshot(obs)
        decision = agent.decide(obs, env)
        obs, reward, done, info = env.step(decision.plan)
        agent.after_step(info, reward)
        s["obs"] = obs
        rec = {"type": "day", "day": info["day"], "before": before, "trace": decision.trace,
               "plan_requested": decision.plan, "plan": info["plan"], "rejected": info["rejected"],
               "events": info["events"], "sales": info["sales"], "reward": reward, "cash": env.cash,
               "profit": env.profit, "tokens": decision.tokens, "cost_usd": decision.cost_usd,
               "latency_s": round(decision.latency_s, 3), "llm_calls": decision.llm_calls,
               "fallback": decision.fallback}
        return json.loads(json.dumps({"done": done, "record": rec, "state": snapshot(obs)}, default=str))


def _header_and_summary(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    header: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    try:
        with path.open(encoding="utf-8") as f:
            first = f.readline()
            header = json.loads(first) if first.strip() else {}
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 20000))
            tail = f.read().decode("utf-8", "ignore").strip().splitlines()
        if tail:
            last = json.loads(tail[-1])
            summary = last if last.get("type") == "summary" else {}
    except (OSError, json.JSONDecodeError):
        pass
    return header, summary


def _coerce(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        try:
            out[k] = float(v) if v not in ("", None) and any(c.isdigit() for c in v) and k != "daily_cash" else v
        except ValueError:
            out[k] = v
    if "daily_cash" in out:
        try:
            out["daily_cash"] = json.loads(out["daily_cash"])
        except (TypeError, json.JSONDecodeError):
            pass
    return out


app.mount("/results", StaticFiles(directory=str(RESULTS_DIR), check_dir=False), name="results")
if (WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> Any:
    target = WEB_DIST / path
    if path and target.is_file():
        return FileResponse(target)
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "UI not built yet. Run: cd web && npm install && npm run build"}
