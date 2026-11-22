"""Prompt text for every agent role. Kept in one place so it is easy to read and tune."""
from __future__ import annotations

import json
from typing import Any

RULES = """GAME (Kaggriculture, official Kaggle rules): a 30-day season, you start with $3000 and a 5x5 field
(25 plots). Score = cash at the end; unsold stock is worth nothing. A Foreman automatically waters,
harvests, weeds, feeds and cares for animals every day - you decide the ECONOMICS.
Crops (seed cost -> units per plot -> base price, days to harvest):
  WHEAT $10 -> 4 -> $25, 4d | CARROT $20 -> 3 -> $35, 3d | TOMATO $50 -> 4 -> $60, 8-11d (ongoing)
  STRAWBERRY $100 -> 4 -> $120, 10-16d (ongoing) | MELON $80 -> 6 -> $250, 10d (8d if fertilised)
Animals (one plot each, eat 1 wheat/day): GOOSE $300 (egg/day ~$50), COW $400 (milk/2d ~$160),
  SHEEP $500 (wool/3d ~$200). Every animal also drops 1 FERTILISER/day (sells ~$100, or doubles crop yield bonus).
Market: prices fall as you sell (premium goods MELON/STRAWBERRY/MILK/WOOL crash fast to $1) and recover
only slowly through town demand. Avoid gluts: diversify crops and spread premium sales.
Land: buy_land unlocks 25 more plots ($1000, then $2000, then $4000). Hands cost $1,1,2,3,5,8,13,21,34,55 per day (max 10); each hand tends ~6 tiles.
Our extension: weather (drought = unwatered plants die, heavy rain = free watering), pests, price shocks."""

PLAN_SCHEMA = """PLAN (all keys optional):
{"plant": {"CROP": plots}, "sell": {"PRODUCT": qty or "all"}, "buy_animals": {"GOOSE": n},
 "fertilise": ["MELON", ...], "hands": n (0-10), "buy_land": true|false}
Crops: WHEAT CARROT TOMATO STRAWBERRY MELON. Products: the crops + EGG MILK WOOL FERTILIZER."""

PROTOCOL = """You work in a loop (ReAct): think, call ONE tool, read its result, repeat; then commit.
Reply with ONE JSON object and nothing else:
{"thought": "<short reasoning>", "action": "<tool name or take_action>", "args": {...}}
To finish: {"thought": "...", "action": "take_action", "args": {"plan": <PLAN>}}
You may call at most {max_tools} tools before take_action. Compare candidate plans with simulate_action."""

ROLES = {
    "single": "You are the AI farm manager. Decide today's complete plan to maximise end-of-season cash.",
    "planner": ("You are the PLANNER in a team. Decide only land use: the keys plant, buy_land, buy_animals. "
                "Think about the whole season: what will be ready before day 29, and what the market can absorb."),
    "market": ("You are the MARKET ANALYST in a team. Decide only the key sell: what to sell today and how much, "
               "so we don't crash prices, but never end the season holding stock."),
    "agronomist": ("You are the AGRONOMIST in a team. Decide only the keys fertilise and hands (labour). "
                   "React to the weather: droughts need enough hands so every plant is watered."),
    "manager": ("You are the MANAGER. Three specialists proposed parts of today's plan. Merge them into one "
                "final plan, check it with simulate_action if useful, fix conflicts (cash!), then take_action."),
}

REFLECT_SYSTEM = """You are a farm manager reviewing a finished season of Kaggriculture.
Write 3-5 short, concrete lessons (each under 25 words) that would increase profit next season.
Reply with ONE JSON object: {"lessons": ["...", "..."]}"""


def system_prompt(role: str, tools_desc: str, lessons: str, max_tools: int) -> str:
    """Full system prompt for a role."""
    return "\n\n".join([
        ROLES[role], RULES, PLAN_SCHEMA,
        "TOOLS:\n" + tools_desc,
        PROTOCOL.replace("{max_tools}", str(max_tools)),
        "LESSONS FROM PREVIOUS SEASONS (long-term memory):\n" + lessons,
    ])


def day_message(obs: dict[str, Any], short_term: str, proposals: dict[str, Any] | None = None) -> str:
    """The user message for one day."""
    state = {k: obs[k] for k in ["day", "days_left", "cash", "free_plots", "crops_growing", "animals", "shed",
                                 "seeds", "next_land_cost", "prices"]}
    state["weather_today"] = obs["weather"]
    parts = [f"TODAY: {json.dumps(state, separators=(',', ':'))}",
             f"RECENT DAYS (short-term memory):\n{short_term}"]
    if proposals is not None:
        parts.append("SPECIALIST PROPOSALS:\n" + json.dumps(proposals, separators=(",", ":")))
    parts.append("Decide today's plan.")
    return "\n\n".join(parts)
