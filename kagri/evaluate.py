"""Evaluate all agents over N seeds and draw the comparison charts.

    python -m kagri.evaluate                      # offline reasoner, 5 seeds (~2-3 min)
    python -m kagri.evaluate --seeds 2            # quicker
    python -m kagri.evaluate --provider gemini --seeds 1 --reflection-episodes 2   # real LLM

Outputs results/*.csv, results/*.png and demo runs in runs/ for the Streamlit replay.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from . import MEMORY_DIR, RESULTS_DIR, RUNS_DIR
from .agents.base import Agent
from .agents.baselines import GreedyAgent, RandomAgent
from .agents.llm_agent import LLMAgent
from .runner import run_episode

AGENT_KEYS = ["random", "greedy", "llm_single", "llm_multi"]


def make_agent(key: str, provider: str, memory_path: Path | None = None, reflection: bool = False) -> Agent:
    """Build an agent by key."""
    if key == "random":
        return RandomAgent()
    if key == "greedy":
        return GreedyAgent()
    return LLMAgent(provider, multi=(key == "llm_multi"), reflection=reflection, memory_path=memory_path)


def _row(summary: dict[str, Any], provider: str, key: str, episode: int = 1) -> dict[str, Any]:
    recs = summary["records"]
    decisions = max(1, len(recs))
    actions: Counter[str] = Counter()
    for r in recs:
        for k, v in r["plan"].items():
            if v:
                actions[k] += 1
    return {
        "agent": key, "label": summary["label"], "provider": provider if key.startswith("llm") else "-",
        "seed": summary["seed"], "episode": episode, "profit": round(summary["profit"]),
        "final_cash": round(summary["final_cash"]), "opponent_cash": round(summary["opponent_cash"]),
        "tokens": summary["tokens"], "cost_usd": round(summary["cost_usd"], 5),
        "llm_calls": summary["llm_calls"], "fallback_days": summary["fallbacks"],
        "latency_per_decision_s": round(summary["latency_s"] / decisions, 3),
        "tool_calls": sum(1 for r in recs for t in r["trace"] if t.get("type") == "tool"),
        "rejected_actions": sum(len(r["rejected"]) for r in recs),
        **{f"n_{k}": actions.get(k, 0) for k in ["plant", "sell", "buy_animals", "fertilise", "hands", "buy_land"]},
        "daily_cash": json.dumps([round(c) for c in summary["daily_cash"]]),
    }


def _job(args: tuple[str, int, str, bool, str | None]) -> dict[str, Any]:
    key, seed, provider, events, log = args
    agent = make_agent(key, provider)
    summary = run_episode(agent, seed, Path(log) if log else None, events=events,
                          meta={"provider": provider if key.startswith("llm") else "-"})
    return _row(summary, provider, key)


def _reflection_job(args: tuple[str, int, str, bool, int, str]) -> list[dict[str, Any]]:
    key, seed, provider, events, episodes, mem = args
    mem_path = Path(mem)
    if mem_path.exists():
        mem_path.unlink()
    agent = make_agent(key, provider, memory_path=mem_path, reflection=True)
    rows = []
    for ep in range(1, episodes + 1):
        s = run_episode(agent, seed, None, events=events, meta={"provider": provider, "episode": ep})
        rows.append(_row(s, provider, key, ep))
    return rows


def _map(fn: Any, jobs: list[Any], parallel: bool) -> list[Any]:
    if parallel and len(jobs) > 1:
        with ProcessPoolExecutor() as ex:
            return list(ex.map(fn, jobs))
    return [fn(j) for j in jobs]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5, help="number of seeds (0..N-1)")
    ap.add_argument("--provider", default="offline", help="offline | gemini | groq | openai | claude")
    ap.add_argument("--agents", default=",".join(AGENT_KEYS), help="comma list of " + ",".join(AGENT_KEYS))
    ap.add_argument("--reflection-episodes", type=int, default=3, help="0 to skip the reflection experiment")
    ap.add_argument("--no-events", action="store_true", help="competition-faithful: no weather/events")
    ap.add_argument("--out", default=str(RESULTS_DIR))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    events = not a.no_events
    parallel = a.provider == "offline"
    keys = [k.strip() for k in a.agents.split(",") if k.strip()]
    t0 = time.time()

    jobs = [(k, s, a.provider, events, str(RUNS_DIR / f"demo_{k}_{a.provider if k.startswith('llm') else 'base'}.jsonl")
             if s == 0 else None) for k in keys for s in range(a.seeds)]
    print(f"Running {len(jobs)} episodes ({', '.join(keys)}; provider={a.provider}; events={events}) ...")
    rows = _map(_job, jobs, parallel)
    df = pd.DataFrame(rows)
    df.to_csv(out / "results.csv", index=False)
    summary = (df.groupby(["agent", "label"], sort=False)
               .agg(mean_profit=("profit", "mean"), std_profit=("profit", "std"), min_profit=("profit", "min"),
                    max_profit=("profit", "max"), mean_tokens=("tokens", "mean"), mean_cost_usd=("cost_usd", "mean"),
                    latency_per_decision_s=("latency_per_decision_s", "mean"), tool_calls=("tool_calls", "mean"),
                    fallback_days=("fallback_days", "mean"))
               .round(1).reset_index())
    summary.to_csv(out / "summary.csv", index=False)
    print(summary[["label", "mean_profit", "std_profit", "mean_tokens", "latency_per_decision_s"]].to_string(index=False))

    refl = pd.DataFrame()
    if a.reflection_episodes > 0:
        rkeys = [k for k in keys if k.startswith("llm")]
        rjobs = [(k, s, a.provider, events, a.reflection_episodes,
                  str(out / f"_mem_{k}_{s}.json")) for k in rkeys for s in range(a.seeds)]
        print(f"Reflection experiment: {len(rjobs)} x {a.reflection_episodes} episodes ...")
        refl = pd.DataFrame([r for rows_ in _map(_reflection_job, rjobs, parallel) for r in rows_])
        refl.to_csv(out / "reflection.csv", index=False)
        for k in rkeys:
            mem = out / f"_mem_{k}_0.json"
            if mem.exists():
                MEMORY_DIR.mkdir(exist_ok=True)
                shutil.copy(mem, MEMORY_DIR / f"lessons_{k.split('_')[1]}_{a.provider}.json")
        for f in out.glob("_mem_*.json"):
            f.unlink()
        print(refl.groupby(["label", "episode"])["profit"].mean().round().to_string())

    from .charts import draw_all
    draw_all(df, refl, out)
    print(f"Done in {time.time() - t0:.0f}s. Results in {out}, replayable runs in {RUNS_DIR}.")


if __name__ == "__main__":
    main()
