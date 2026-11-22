"""The ReAct agent loop, guardrails and memory (offline reasoner and a scripted fake LLM)."""
import json

from kagri.agents.llm_agent import LLMAgent, parse_json
from kagri.env import FarmEnv
from kagri.llm.providers import LLMReply, Provider
from kagri.runner import run_episode


class ScriptedLLM(Provider):
    """Replays canned replies, to test the loop without a network."""

    name = "scripted"

    def __init__(self, replies):
        super().__init__()
        self.replies = list(replies)
        self.min_interval = 0

    def respond(self, system, messages, ctx=None):
        return LLMReply(self.replies.pop(0) if self.replies else "garbage", 10, 5)


def test_parse_json_handles_fences_and_chatter():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"action": "x", "args": {"y": {"z": 2}}} hope it helps')["args"]["y"]["z"] == 2
    assert parse_json("no json here") is None


def test_react_loop_calls_tools_then_acts(tmp_path):
    replies = [
        json.dumps({"thought": "check weather", "action": "get_weather_forecast", "args": {}}),
        "this is not json",
        json.dumps({"thought": "simulate", "action": "simulate_action", "args": {"plan": {"plant": {"WHEAT": 5}}}}),
        json.dumps({"thought": "go", "action": "take_action", "args": {"plan": {"plant": {"WHEAT": 5}, "hands": 1}}}),
    ]
    agent = LLMAgent(ScriptedLLM(replies), reflection=False, memory_path=tmp_path / "m.json")
    env = FarmEnv()
    obs = env.reset(0)
    agent.begin_episode(0)
    d = agent.decide(obs, env)
    kinds = [t["type"] for t in d.trace]
    assert kinds.count("tool") == 2 and "error" in kinds and kinds[-1] == "action"
    assert d.plan["plant"] == {"WHEAT": 5} and not d.fallback and d.tokens == 60


def test_bad_llm_falls_back_safely(tmp_path):
    agent = LLMAgent(ScriptedLLM([]), reflection=False, memory_path=tmp_path / "m.json")
    env = FarmEnv()
    obs = env.reset(0)
    agent.begin_episode(0)
    d = agent.decide(obs, env)
    assert d.fallback and d.plan["plant"]


def test_offline_multi_agent_and_reflection(tmp_path):
    agent = LLMAgent("offline", multi=True, reflection=True, memory_path=tmp_path / "m.json")
    s = run_episode(agent, seed=0)
    roles = {t["agent"] for r in s["records"] for t in r["trace"]}
    assert {"planner", "market", "agronomist", "manager"} <= roles
    assert s["profit"] > 30000 and s["fallbacks"] == 0
    assert agent.ltm.entries and agent.ltm.entries[0]["lessons"]
