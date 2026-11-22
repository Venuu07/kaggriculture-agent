"""Ablation study: switch off one component of the agent at a time and measure the profit lost.

    python -m kagri.ablation             # 5 seeds, offline reasoner (~2 min)
    python -m kagri.ablation --seeds 3

Writes results/ablation.csv and results/ablation.png.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import pandas as pd

from . import RESULTS_DIR
from .agents.llm_agent import LLMAgent
from .runner import run_episode

# name -> (multi-agent?, overrides, what it removes)
VARIANTS: dict[str, tuple[bool, dict[str, Any], str]] = {
    "Full system": (True, {}, "multi-agent team, look-ahead, glut-aware mix, land, animals"),
    "No team (single agent)": (False, {}, "one ReAct agent instead of four roles"),
    "No look-ahead": (True, {"no_lookahead": True}, "plans are never simulated before acting"),
    "No glut-awareness": (True, {"naive_mix": True}, "all plots go to the best single-plot crop"),
    "No animals": (True, {"allow_animals": False}, "never buys geese, cows or sheep"),
    "No land expansion": (True, {"allow_land": False}, "stays on the first 5x5 field"),
    "Small workforce (max 4 hands)": (True, {"hands_cap": 4}, "labour capped at 4 hired hands"),
}


def _job(args: tuple[str, int, bool]) -> dict[str, Any]:
    name, seed, events = args
    multi, overrides, _ = VARIANTS[name]
    agent = LLMAgent("offline", multi=multi, reflection=False, overrides=overrides, tag=name)
    s = run_episode(agent, seed, None, events=events)
    return {"variant": name, "seed": seed, "profit": round(s["profit"])}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--no-events", action="store_true")
    a = ap.parse_args(argv)
    jobs = [(n, s, not a.no_events) for n in VARIANTS for s in range(a.seeds)]
    print(f"Ablation: {len(VARIANTS)} variants x {a.seeds} seeds ...")
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_job, jobs))
    df = pd.DataFrame(rows)
    full = df[df.variant == "Full system"].set_index("seed")["profit"]
    df["delta_vs_full"] = df.apply(lambda r: r["profit"] - full[r["seed"]], axis=1)
    summary = (df.groupby("variant", sort=False)
               .agg(mean_profit=("profit", "mean"), std_profit=("profit", "std"),
                    mean_delta=("delta_vs_full", "mean"),
                    seeds_worse=("delta_vs_full", lambda d: int((d < 0).sum())))
               .round(0).reset_index())
    summary["removes"] = summary["variant"].map(lambda n: VARIANTS[n][2])
    summary["delta_pct"] = (100 * summary["mean_delta"] / summary.loc[0, "mean_profit"]).round(1)
    RESULTS_DIR.mkdir(exist_ok=True)
    df.to_csv(RESULTS_DIR / "ablation_runs.csv", index=False)
    summary.to_csv(RESULTS_DIR / "ablation.csv", index=False)
    print(summary[["variant", "mean_profit", "mean_delta", "delta_pct", "seeds_worse"]].to_string(index=False))
    from .charts import ablation_chart
    ablation_chart(summary, RESULTS_DIR)


if __name__ == "__main__":
    main()
