"""Record one full season to runs/ so the demo can replay it offline.

    python -m kagri.record --agent llm_single --provider gemini --seed 0
    python -m kagri.record --agent llm_multi --provider gemini --seed 0 --days 10   # shorter, fewer API calls

With a free Gemini key a full single-agent season is ~90-120 LLM calls (about 8-12 minutes
with the default 4 s spacing). Falls back safely (and says so) if the API fails mid-run.
"""
from __future__ import annotations

import argparse
import time

from . import RUNS_DIR
from .evaluate import make_agent
from .llm.providers import provider_ready
from .runner import run_episode


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", default="llm_single", choices=["random", "greedy", "llm_single", "llm_multi"])
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-events", action="store_true")
    ap.add_argument("--reflection", action="store_true", help="use and update long-term lessons in memory/")
    ap.add_argument("--test-before-act", action="store_true",
                    help="policy: the agent must simulate a plan before committing to it")
    a = ap.parse_args(argv)
    ok, why = provider_ready(a.provider)
    if a.agent.startswith("llm") and not ok:
        raise SystemExit(f"Cannot record with {a.provider}: {why}. Copy .env.example to .env and add the key.")
    agent = make_agent(a.agent, a.provider, reflection=a.reflection, test_before_act=a.test_before_act)
    stamp = time.strftime("%Y%m%d_%H%M")
    suffix = "_tba" if a.test_before_act else ""
    path = RUNS_DIR / f"recorded_{a.agent}{suffix}_{a.provider}_seed{a.seed}_{stamp}.jsonl"

    def progress(rec: dict, obs: dict) -> None:
        flag = " (FALLBACK)" if rec["fallback"] else ""
        print(f"day {rec['day']:2d}: cash ${rec['cash']:>9,.0f}  calls {rec['llm_calls']}  "
              f"tokens {rec['tokens']}{flag}", flush=True)

    s = run_episode(agent, a.seed, path, events=not a.no_events, on_day=progress,
                    meta={"provider": a.provider, "model": getattr(agent, "provider", None) and agent.provider.model})
    print(f"\nProfit ${s['profit']:,.0f} | LLM calls {s['llm_calls']} | tokens {s['tokens']} | "
          f"est. cost ${s['cost_usd']:.4f} | fallback days {s['fallbacks']}\nSaved {path}")


if __name__ == "__main__":
    main()
