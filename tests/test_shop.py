"""The second world: the same agent core running a kirana store."""
from kagri.agents.core import react_loop
from kagri.shop import agent as shop_agent
from kagri.shop.agent import ShopAgent, run_shop
from kagri.shop.env import ShopEnv


def test_shop_is_deterministic_and_validates():
    a, b = ShopEnv(), ShopEnv()
    a.reset(3), b.reset(3)
    plan = {"order": {"MILK": 50, "PIZZA": 3, "RICE": "lots"}, "price": {"MILK": 999}}
    _, ra, _, info = a.step(plan)
    _, rb, _, _ = b.step(plan)
    assert ra == rb and len(info["rejected"]) == 3 and info["plan"]["price"]["MILK"] == 45


def test_shop_uses_the_same_react_core():
    assert shop_agent.react_loop is react_loop
    env = ShopEnv()
    obs = env.reset(0)
    d = ShopAgent("offline").decide(obs, env)
    assert any(t["type"] == "tool" and t["name"] == "simulate_plan" for t in d["trace"]) and not d["fallback"]


def test_agent_beats_fixed_rule():
    agent = sum(run_shop("agent", s)["profit"] for s in range(2))
    base = sum(run_shop("baseline", s)["profit"] for s in range(2))
    assert agent > base
