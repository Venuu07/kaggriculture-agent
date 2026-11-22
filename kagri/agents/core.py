"""The domain-neutral agent core: one ReAct loop shared by every world (farm, shop, ...).

A world plugs in only three things: a toolbox (describe/call), a system prompt and the first
user message. The loop itself (think, call one tool, read the result, repeat, commit) and its
guardrails (tool budget, allowed tools, JSON retries, test-before-act) are identical everywhere.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, Protocol

from ..llm.providers import Provider


class Toolbox(Protocol):
    def describe(self, allowed: list[str] | None = None) -> str: ...
    def call(self, name: str, args: Any) -> dict[str, Any]: ...


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


def compact(obj: Any, limit: int = 1800) -> str:
    """JSON-encode a tool result, trimmed so prompts stay small."""
    s = json.dumps(obj, default=str, separators=(",", ":"))
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


def react_loop(*, provider: Provider, system: str, first_message: str, toolbox: Toolbox, role: str,
               ctx: dict[str, Any], trace: list[dict[str, Any]], account: Callable[[Any], None],
               max_tools: int, max_retries: int, allowed: list[str] | None = None,
               keep_keys: list[str] | None = None, test_before_act: bool = False,
               simulate_tool: str = "simulate_action") -> dict[str, Any] | None:
    """Run think -> tool -> observe until the model commits a plan. Returns the plan, or None if the
    model could not produce a usable reply (the caller then falls back to a safe plan)."""
    messages = [{"role": "user", "content": first_message}]
    steps: list[dict[str, Any]] = []
    tool_calls = bad_json = forced = 0
    nudged = False
    while True:
        reply = provider.respond(system, messages, {**ctx, "role": role, "steps": steps})
        account(reply)
        parsed = parse_json(reply.text)
        if parsed is None or "action" not in parsed:
            bad_json += 1
            trace.append({"type": "error", "agent": role, "text": f"invalid JSON reply #{bad_json}: {reply.text[:200]}"})
            if bad_json > max_retries:
                return None
            messages += [{"role": "assistant", "content": reply.text or "(empty)"},
                         {"role": "user", "content": 'Invalid reply. Answer with ONE JSON object: '
                                                     '{"thought": "...", "action": "...", "args": {...}}'}]
            continue
        thought = str(parsed.get("thought", ""))
        action = str(parsed.get("action", ""))
        args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
        trace.append({"type": "thought", "agent": role, "text": thought})
        if (action in ("take_action", "final") and test_before_act and not nudged and tool_calls < max_tools
                and not any(st["name"] == simulate_tool for st in steps)):
            nudged = True
            trace.append({"type": "guardrail", "agent": role,
                          "text": "Test-before-act policy: simulate the plan before committing."})
            messages += [{"role": "assistant", "content": reply.text},
                         {"role": "user", "content": f'Before committing, test this plan with {simulate_tool} '
                          '(args: {"plan": <your plan>, "days": 8}), compare it with at least one alternative '
                          'if you have tool calls left, then take_action with the better plan.'}]
            continue
        if action in ("take_action", "final", "propose"):
            plan = args.get("plan", args)
            if not isinstance(plan, dict):
                plan = {}
            if keep_keys is not None:
                plan = {k: v for k, v in plan.items() if k in keep_keys}
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
