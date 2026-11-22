"""The agentic AI farm manager: a ReAct tool-using LLM agent with memory, reflection and an
optional multi-agent team (Planner, Market Analyst, Agronomist, coordinated by a Manager).

Per day:  think -> call a tool -> observe -> ... -> take_action(plan)
Guardrails: plan validation + budget checks (kagri/plan.py), max tool calls per turn,
retry on bad JSON, safe fallback plan, token / cost / latency counters.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..config import load_config
from ..env import FarmEnv
from ..llm.providers import LLMError, Provider, get_provider
from .base import Agent, Decision
from .memory import LongTermMemory, ShortTermMemory
from .prompts import REFLECT_SYSTEM, day_message, system_prompt
from .strategy import strategic_plan
from .tools import ToolBox, compact

ROLE_TOOLS = {
    "single": None,
    "planner": ["plan_crop_mix", "estimate_crop_profit", "estimate_animal_profit", "simulate_action", "get_farm_state"],
    "market": ["get_market_prices", "estimate_sale", "get_farm_state"],
    "agronomist": ["get_weather_forecast", "get_farm_state"],
    "manager": ["simulate_action", "get_farm_state"],
}
ROLE_KEYS = {"planner": ["plant", "buy_land", "buy_animals"], "market": ["sell"],
             "agronomist": ["fertilise", "hands"]}


def parse_json(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of a model reply (handles ```json fences and chatter)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


class LLMAgent(Agent):
    """ReAct agent. `multi=True` switches on the specialist team; `reflection=True` learns across seasons."""

    def __init__(self, provider: Provider | str | None = None, multi: bool = False, reflection: bool = True,
                 memory_path: Path | None = None) -> None:
        self.provider = provider if isinstance(provider, Provider) else get_provider(provider)
        self.multi = multi
        self.reflection = reflection
        cfg = load_config()["llm"]
        self.max_tools = int(cfg["max_tool_calls_per_turn"])
        self.max_retries = int(cfg["max_json_retries"])
        self.provider.temperature = float(cfg["temperature"])
        mode = "multi" if multi else "single"
        self.name = f"llm_{mode}"
        self.label = f"LLM {mode}-agent ({self.provider.name})"
        self.ltm = LongTermMemory(f"{mode}_{self.provider.name}", memory_path)
        self.stm = ShortTermMemory()
        self.episode = 0

    # ------------------------------------------------------------ episode
    def begin_episode(self, seed: int) -> None:
        self.stm = ShortTermMemory()
        self.seed = seed
        self.params = self.ltm.params() if self.reflection else {}
        self.lessons_text = self.ltm.render() if self.reflection else "(reflection disabled)"

    def after_step(self, info: dict[str, Any], reward: float) -> None:
        self.stm.add(info["day"], info["plan"], reward, info["events"], info["rejected"])

    def decide(self, obs: dict[str, Any], env: FarmEnv) -> Decision:
        self._stats = {"tokens": 0, "cost": 0.0, "latency": 0.0, "calls": 0}
        toolbox = ToolBox(env, obs)
        trace: list[dict[str, Any]] = []
        try:
            plan = self._team(obs, env, toolbox, trace) if self.multi else \
                self._react("single", obs, env, toolbox, trace)
        except LLMError as e:
            trace.append({"type": "error", "agent": "system", "text": str(e)})
            plan = None
        fallback = plan is None
        if fallback:
            plan = strategic_plan(obs, self.params)
            trace.append({"type": "fallback", "agent": "system",
                          "text": "LLM reply unusable - using the deterministic safe plan.", "plan": plan})
        return Decision(plan=plan, trace=trace, tokens=self._stats["tokens"], cost_usd=self._stats["cost"],
                        latency_s=self._stats["latency"], llm_calls=self._stats["calls"], fallback=fallback)

    # ----------------------------------------------------------- ReAct core
    def _react(self, role: str, obs: dict[str, Any], env: FarmEnv, toolbox: ToolBox, trace: list[dict[str, Any]],
               proposals: dict[str, Any] | None = None) -> dict[str, Any] | None:
        allowed = ROLE_TOOLS[role]
        max_tools = self.max_tools if role in ("single", "planner") else 2
        system = system_prompt(role, toolbox.describe(allowed), self.lessons_text, max_tools)
        messages = [{"role": "user", "content": day_message(obs, self.stm.render(), proposals)}]
        steps: list[dict[str, Any]] = []
        tool_calls = bad_json = forced = 0
        while True:
            ctx = {"role": role, "obs": obs, "env": env, "steps": steps, "params": self.params,
                   "proposals": proposals}
            reply = self.provider.respond(system, messages, ctx)
            self._account(reply)
            parsed = parse_json(reply.text)
            if parsed is None or "action" not in parsed:
                bad_json += 1
                trace.append({"type": "error", "agent": role, "text": f"invalid JSON reply #{bad_json}: {reply.text[:200]}"})
                if bad_json > self.max_retries:
                    return None
                messages += [{"role": "assistant", "content": reply.text or "(empty)"},
                             {"role": "user", "content": 'Invalid reply. Answer with ONE JSON object: '
                                                         '{"thought": "...", "action": "...", "args": {...}}'}]
                continue
            thought = str(parsed.get("thought", ""))
            action = str(parsed.get("action", ""))
            args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
            trace.append({"type": "thought", "agent": role, "text": thought})
            if action in ("take_action", "final", "propose"):
                plan = args.get("plan", args)
                if not isinstance(plan, dict):
                    plan = {}
                if role in ROLE_KEYS:
                    plan = {k: v for k, v in plan.items() if k in ROLE_KEYS[role]}
                trace.append({"type": "action", "agent": role, "plan": plan})
                return plan
            if tool_calls >= max_tools or (allowed is not None and action not in allowed):
                forced += 1
                why = "Tool budget used up" if tool_calls >= max_tools else f"Tool '{action}' is not available to you"
                trace.append({"type": "guardrail", "agent": role, "text": why})
                if forced > 2:
                    return None
                messages += [{"role": "assistant", "content": reply.text},
                             {"role": "user", "content": f"{why}. Reply now with action take_action and your plan."}]
                continue
            t0 = time.perf_counter()
            result = toolbox.call(action, args)
            steps.append({"name": action, "args": args, "result": result})
            trace.append({"type": "tool", "agent": role, "name": action, "args": args, "result": result,
                          "ms": round(1000 * (time.perf_counter() - t0))})
            tool_calls += 1
            messages += [{"role": "assistant", "content": reply.text},
                         {"role": "user", "content": f"Result of {action}: {compact(result)}"}]

    def _team(self, obs: dict[str, Any], env: FarmEnv, toolbox: ToolBox,
              trace: list[dict[str, Any]]) -> dict[str, Any] | None:
        proposals: dict[str, Any] = {}
        for role in ("planner", "market", "agronomist"):
            part = self._react(role, obs, env, toolbox, trace)
            proposals[role] = part if part is not None else {}
            if part is None:
                trace.append({"type": "guardrail", "agent": role, "text": "no usable proposal; manager decides alone"})
        return self._react("manager", obs, env, toolbox, trace, proposals)

    def _account(self, reply: Any) -> None:
        self._stats["tokens"] += reply.tokens
        self._stats["cost"] += self.provider.cost(reply)
        self._stats["latency"] += reply.latency_s
        self._stats["calls"] += 1 if self.provider.name != "offline" else 0

    # ----------------------------------------------------------- reflection
    def end_episode(self, summary: dict[str, Any]) -> None:
        self.episode += 1
        if not self.reflection:
            return
        evidence = season_evidence(summary)
        try:
            reply = self.provider.respond(REFLECT_SYSTEM, [{"role": "user", "content": json.dumps(evidence)}],
                                          {"role": "reflect", "evidence": evidence, "params": self.params})
            parsed = parse_json(reply.text) or {}
        except LLMError:
            parsed = {}
        lessons = [str(x) for x in parsed.get("lessons", [])][:5]
        if lessons:
            self.ltm.add({"episode": len(self.ltm.entries) + 1, "seed": self.seed, "profit": round(summary["profit"]),
                          "lessons": lessons, "params": parsed.get("params", {})})


def season_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    """Facts about a finished season that reflection reasons over."""
    from ..engine import kaggriculture as kg
    sold: dict[str, list[float]] = {}
    for r in summary["records"]:
        for item, (units, revenue) in r["sales"].items():
            s = sold.setdefault(item, [0, 0.0])
            s[0] += units
            s[1] += revenue
    sales = {item: {"units": u, "avg_price": round(rev / max(1, u), 1), "base": kg.MARKET_PARAMS[item]["base"]}
             for item, (u, rev) in sold.items()}
    recs = summary["records"]
    early_cash = [r["cash"] for r in recs[:10]]
    return {
        "profit": round(summary["profit"]), "opponent_cash": summary["opponent_cash"],
        "sales": sales,
        "land_bought_days": [r["day"] for r in recs if r["plan"].get("buy_land")],
        "animals_bought": sum(sum(r["plan"].get("buy_animals", {}).values()) for r in recs),
        "max_weeds": max((r["before"]["weeds"] for r in recs), default=0),
        "avg_cash_first_10_days": round(sum(early_cash) / max(1, len(early_cash))),
        "avg_hands": round(sum(r["plan"].get("hands", 0) for r in recs) / max(1, len(recs)), 1),
        "events": [e for r in recs for e in r["events"].get("events", [])][:10],
        "rejected_actions": sum(len(r["rejected"]) for r in recs),
        "fallback_days": sum(1 for r in recs if r["fallback"]),
        "final_unsold_stock": summary.get("final", {}).get("shed", {}),
        "animals_bought_after_day_15": sum(sum(r["plan"].get("buy_animals", {}).values()) for r in recs if r["day"] > 15),
    }
