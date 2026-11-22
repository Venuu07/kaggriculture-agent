"""Verified reflection: lessons are hypotheses, tested in simulation before they are adopted.

After each training season the reflector reads the season's evidence and proposes lessons, each
tied to a concrete strategy change. Every candidate is played on separate validation seasons;
only a lesson that raises validation profit is adopted. Progress is measured on held-out test
seasons the learner never trained or validated on.

The learner starts as a "novice farmer" (crops only: no animals, no land), to test whether
reflection can rediscover the investments the ablation study showed are valuable.

    python -m kagri.reflection              # 5 seasons (~2 min offline)

Writes results/reflection_verified.csv, results/reflection_verified.png and
memory/lessons_verified.json.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable

import pandas as pd

from . import MEMORY_DIR, RESULTS_DIR
from .agents.llm_agent import LLMAgent, season_evidence
from .runner import run_episode

NOVICE = {"allow_animals": False, "allow_land": False}
TRAIN_SEEDS = [10, 11, 12, 13, 14, 15, 16, 17]
VAL_SEEDS = [100, 101, 102, 103]
TEST_SEEDS = [200, 201, 202, 203]
MIN_GAIN = 0.01

Params = dict[str, Any]
Hypothesis = tuple[str, Callable[[Params, dict[str, Any]], tuple[str, Params] | None]]


def _h_animals(p: Params, ev: dict[str, Any]) -> tuple[str, Params] | None:
    if p.get("allow_animals", True):
        return None
    return ("Never bought an animal. Each animal drops ~1 fertiliser a day (~$100) plus eggs, milk or wool, "
            "so buy animals early.", {**p, "allow_animals": True})


def _h_land(p: Params, ev: dict[str, Any]) -> tuple[str, Params] | None:
    if p.get("allow_land", True):
        return None
    return (f"Stayed on one 5x5 field all season and ended with ${ev['profit']:,} profit. More land means more "
            "plots: buy the next quadrant once cash allows.", {**p, "allow_land": True})


def _h_glut(p: Params, ev: dict[str, Any]) -> tuple[str, Params] | None:
    worst = None
    for item, s in ev["sales"].items():
        if item in ("MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT") and s["units"] >= 20:
            ratio = s["avg_price"] / s["base"]
            if worst is None or ratio < worst[1]:
                worst = (item, ratio, s)
    if worst is None or worst[1] > 0.8:
        return None
    item, ratio, s = worst
    key = f"bias_{item}"
    return (f"{item.title()} sold at ${s['avg_price']} on average vs ${s['base']} base ({ratio:.0%}): "
            f"we flooded the market. Plant fewer {item.lower()}.", {**p, key: round(p.get(key, 1.0) * 0.85, 3)})


def _h_hands(p: Params, ev: dict[str, Any]) -> tuple[str, Params] | None:
    if ev["max_weeds"] < 5 or p.get("hands_bonus", 0) >= 2:
        return None
    return (f"Up to {ev['max_weeds']} weeds at once: plants were dying or plots sat idle. Hire one more hand.",
            {**p, "hands_bonus": p.get("hands_bonus", 0) + 1})


def _h_lookahead(p: Params, ev: dict[str, Any]) -> tuple[str, Params] | None:
    d = int(p.get("lookahead_days", 5))
    if d >= 8:
        return None
    return (f"Investments pay back over 8-10 days but I only simulated {d} days ahead. Look further ahead.",
            {**p, "lookahead_days": 8})


def _h_patience(p: Params, ev: dict[str, Any]) -> tuple[str, Params] | None:
    premium = [i for i in ("MELON", "STRAWBERRY", "MILK", "WOOL") if i in ev["sales"]]
    if not premium or p.get("sell_floor", 0.65) >= 0.8:
        return None
    return (f"Premium goods ({', '.join(x.lower() for x in premium)}) crash fast when dumped. "
            "Hold them back until prices recover.", {**p, "sell_floor": round(p.get("sell_floor", 0.65) + 0.1, 2)})


HYPOTHESES: list[Hypothesis] = [("animals", _h_animals), ("land", _h_land), ("glut", _h_glut),
                                ("labour", _h_hands), ("lookahead", _h_lookahead), ("patience", _h_patience)]


def _play(args: tuple[Params, int]) -> float:
    params, seed = args
    agent = LLMAgent("offline", multi=False, reflection=False, overrides=params)
    return run_episode(agent, seed)["profit"]


def _mean_profit(ex: ProcessPoolExecutor, params_list: list[Params], seeds: list[int]) -> list[float]:
    jobs = [(p, s) for p in params_list for s in seeds]
    res = list(ex.map(_play, jobs))
    k = len(seeds)
    return [sum(res[i * k:(i + 1) * k]) / k for i in range(len(params_list))]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", type=int, default=5)
    a = ap.parse_args(argv)
    params: Params = dict(NOVICE)
    rows: list[dict[str, Any]] = []
    lessons: list[dict[str, Any]] = []
    with ProcessPoolExecutor() as ex:
        test0 = _mean_profit(ex, [params], TEST_SEEDS)[0]
        rows.append({"season": 0, "test_profit": round(test0), "adopted": "(novice start)", "lesson": ""})
        print(f"season 0 (novice): test profit ${test0:,.0f}")
        for season in range(1, a.seasons + 1):
            seed = TRAIN_SEEDS[(season - 1) % len(TRAIN_SEEDS)]
            agent = LLMAgent("offline", multi=False, reflection=False, overrides=params)
            ev = season_evidence(run_episode(agent, seed))
            cands = [(hid, *out) for hid, fn in HYPOTHESES if (out := fn(params, ev)) is not None]
            scores = _mean_profit(ex, [params] + [c[2] for c in cands], VAL_SEEDS)
            base, tried = scores[0], []
            best = None
            for (hid, text, newp), sc in zip(cands, scores[1:]):
                gain = (sc - base) / max(1.0, abs(base))
                tried.append({"hypothesis": hid, "val_gain_pct": round(100 * gain, 1)})
                if gain >= MIN_GAIN and (best is None or sc > best[3]):
                    best = (hid, text, newp, sc, gain)
            if best:
                params = best[2]
                lessons.append({"episode": season, "seed": seed, "profit": ev["profit"],
                                "lessons": [f"{best[1]} (verified: {best[4]:+.0%} on validation seasons)"],
                                "params": params, "tried": tried})
            test = _mean_profit(ex, [params], TEST_SEEDS)[0]
            rows.append({"season": season, "test_profit": round(test), "adopted": best[0] if best else "none",
                         "lesson": best[1] if best else "no candidate improved validation profit",
                         "tried": json.dumps(tried)})
            print(f"season {season}: adopted {rows[-1]['adopted']:<10} test profit ${test:,.0f}  tried {tried}")
    df = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(exist_ok=True)
    df.to_csv(RESULTS_DIR / "reflection_verified.csv", index=False)
    MEMORY_DIR.mkdir(exist_ok=True)
    (MEMORY_DIR / "lessons_verified.json").write_text(json.dumps(lessons, indent=2), encoding="utf-8")
    from .charts import verified_reflection_chart
    verified_reflection_chart(df, RESULTS_DIR)


if __name__ == "__main__":
    main()
