"""Arena: two farmers, one shared market. A round-robin tournament between our agents and
Kaggle's own built-in bot, rated with Bradley-Terry (the method Kaggriculture used).

    python -m kagri.arena                # 3 seeds x both seat orders (~3 min offline)
    python -m kagri.arena --seeds 2

Research question: what does competing on a shared market cost? Each agent plays the weak
Kaggle starter bot and a copy of itself; the gap is the price of competition.

Writes results/arena_games.csv, arena_ratings.csv, arena_matrix.csv, arena.png and
runs/arena_<a>_vs_<b>.jsonl (a showcase match for the side-by-side replay in the UI).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from . import RESULTS_DIR, RUNS_DIR
from .agents.base import Agent
from .env import FarmEnv
from .evaluate import make_agent
from .runner import snapshot

PARTICIPANTS = {
    "kaggle_starter": "Kaggle starter bot",
    "random": "Random",
    "greedy": "Greedy heuristic",
    "llm_single": "LLM single-agent",
    "llm_multi": "LLM multi-agent",
}
BUILTIN = {"kaggle_starter": "starter"}


def play_match(a: str, b: str, seed: int, events: bool = True, provider: str = "offline",
               log: Path | None = None) -> dict[str, Any]:
    """Play one season with `a` in seat 0 and `b` in seat 1 on a shared market."""
    env = FarmEnv(events=events)
    env.reset(seed)
    seats = [a, b]
    agents: dict[int, Agent] = {}
    for i, key in enumerate(seats):
        if key not in BUILTIN:
            agents[i] = make_agent(key, provider)
            agents[i].begin_episode(seed)
    if not agents:
        raise ValueError("at least one seat must be one of our agents")
    driver = min(agents)  # the seat whose view steps the game
    days: list[dict[str, Any]] = []
    base = env
    while not base.done:
        views = {0: base.view(0), 1: base.view(1)}
        obs = {i: views[i].observe() for i in (0, 1)}
        plans = {i: agents[i].decide(obs[i], views[i]) for i in agents}
        other = 1 - driver
        rival = plans[other].plan if other in plans else BUILTIN[seats[other]]
        _, reward, _, info = views[driver].step(plans[driver].plan, rival=rival)
        base = views[driver]
        rewards = {driver: reward}
        infos = {driver: info}
        if "rival" in info:
            rewards[other] = info["rival"]["reward"]
            infos[other] = {"day": info["day"], "plan": info["rival"]["plan"], "events": info["events"],
                            "rejected": info["rival"]["rejected"]}
        for i, ag in agents.items():
            ag.after_step(infos[i], rewards[i])
        if log is not None:
            days.append({"day": info["day"], "events": info["events"],
                         "players": [{"before": snapshot(obs[i]),
                                      "plan": infos[i]["plan"] if i in infos else None,
                                      "trace": plans[i].trace if i in plans else [],
                                      "reward": rewards.get(i)} for i in (0, 1)]})
    cash = [base.view(i).cash for i in (0, 1)]
    result = {"seed": seed, "p0": a, "p1": b, "cash0": round(cash[0]), "cash1": round(cash[1]),
              "profit0": round(cash[0] - env.starting_money), "profit1": round(cash[1] - env.starting_money),
              "winner": a if cash[0] > cash[1] else b if cash[1] > cash[0] else "tie"}
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        final = [snapshot(base.view(i).observe()) for i in (0, 1)]
        with log.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "arena_header", "seed": seed, "events": events, "provider": provider,
                                "players": [{"key": k, "label": PARTICIPANTS[k]} for k in seats]}) + "\n")
            for d in days:
                f.write(json.dumps({"type": "arena_day", **d}, default=str) + "\n")
            f.write(json.dumps({"type": "arena_summary", **result, "final": final}) + "\n")
    return result


def _job(args: tuple[str, str, int, bool]) -> dict[str, Any]:
    return play_match(*args)


def bradley_terry(games: pd.DataFrame, keys: list[str], iters: int = 200) -> dict[str, float]:
    """Bradley-Terry strengths by the MM algorithm (ties = half a win each), on an Elo-like scale."""
    wins = {k: 0.0 for k in keys}
    n: dict[tuple[str, str], int] = {}
    for _, g in games.iterrows():
        a, b = g["p0"], g["p1"]
        if a == b:
            continue
        pair = tuple(sorted((a, b)))
        n[pair] = n.get(pair, 0) + 1
        if g["winner"] == "tie":
            wins[a] += 0.5
            wins[b] += 0.5
        else:
            wins[g["winner"]] += 1
    p = {k: 1.0 for k in keys}
    for _ in range(iters):
        new = {}
        for k in keys:
            denom = sum(cnt / (p[x] + p[y]) for (x, y), cnt in n.items() if k in (x, y))
            new[k] = max(wins[k], 0.05) / denom if denom else p[k]
        mean = math.exp(sum(math.log(v) for v in new.values()) / len(new))
        p = {k: v / mean for k, v in new.items()}
    return {k: round(1500 + 400 * math.log10(v), 0) for k, v in p.items()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--no-events", action="store_true")
    a = ap.parse_args(argv)
    events = not a.no_events
    keys = list(PARTICIPANTS)
    pairs = [(x, y) for x, y in itertools.combinations(keys, 2)]
    pairs += [(k, k) for k in keys if k not in BUILTIN]
    jobs = []
    for (x, y), s in itertools.product(pairs, range(a.seeds)):
        jobs.append((x, y, s, events))
        if x != y:
            jobs.append((y, x, s, events))
    print(f"Arena: {len(jobs)} matches ({len(pairs)} pairings x {a.seeds} seeds x both seats) ...")
    with ProcessPoolExecutor() as ex:
        games = pd.DataFrame(list(ex.map(_job, jobs)))
    RESULTS_DIR.mkdir(exist_ok=True)
    games.to_csv(RESULTS_DIR / "arena_games.csv", index=False)

    ratings = bradley_terry(games, keys)
    long = pd.concat([
        games.rename(columns={"p0": "agent", "p1": "opponent", "profit0": "profit"})[["agent", "opponent", "profit", "winner"]],
        games.rename(columns={"p1": "agent", "p0": "opponent", "profit1": "profit"})[["agent", "opponent", "profit", "winner"]],
    ])
    long = long[long["agent"].isin([k for k in keys if k not in BUILTIN]) | (long["agent"] == "kaggle_starter")]
    matrix = long.groupby(["agent", "opponent"])["profit"].mean().unstack().reindex(index=keys, columns=keys).round(0)
    matrix.to_csv(RESULTS_DIR / "arena_matrix.csv")
    rows = []
    for k in keys:
        mine = long[(long["agent"] == k) & (long["opponent"] != k)]
        decided = mine[mine["winner"] != "tie"]
        rows.append({"agent": k, "label": PARTICIPANTS[k], "rating": ratings[k],
                     "win_rate": round(100 * (decided["winner"] == k).sum() / max(1, len(mine)), 1),
                     "mean_profit": round(mine["profit"].mean()),
                     "vs_starter": matrix.loc[k, "kaggle_starter"] if k != "kaggle_starter" else None,
                     "vs_itself": matrix.loc[k, k] if k not in BUILTIN else None})
    table = pd.DataFrame(rows).sort_values("rating", ascending=False)
    table["competition_cost_pct"] = (100 * (table["vs_itself"] - table["vs_starter"]) / table["vs_starter"]).round(1)
    table.to_csv(RESULTS_DIR / "arena_ratings.csv", index=False)
    print(table.to_string(index=False))

    log = RUNS_DIR / "arena_llm_multi_vs_greedy.jsonl"
    play_match("llm_multi", "greedy", 0, events, log=log)
    print(f"Showcase match saved to {log}")
    from .charts import arena_chart
    arena_chart(table, RESULTS_DIR)


if __name__ == "__main__":
    main()
