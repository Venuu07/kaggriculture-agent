"""Two farmers on one shared market."""
import pandas as pd

from kagri.arena import bradley_terry, play_match
from kagri.env import FarmEnv


def test_two_agents_share_one_market(tmp_path):
    log = tmp_path / "m.jsonl"
    r = play_match("greedy", "llm_single", seed=1, log=log)
    assert r["winner"] in ("greedy", "llm_single", "tie")
    assert r["profit0"] != 0 and r["profit1"] != 0
    assert len(log.read_text().splitlines()) == 32  # header + 30 days + summary


def test_seat_views_see_their_own_farm():
    env = FarmEnv()
    env.reset(0)
    env.view(0).step({"plant": {"WHEAT": 10}, "hands": 1}, rival={"plant": {"CARROT": 5}, "hands": 1})
    a, b = env.view(0).observe(), env.view(1).observe()
    assert a["crops_growing"].get("WHEAT") == 10 and b["crops_growing"].get("CARROT") == 5
    assert a["opponent_cash"] == b["cash"]


def test_bradley_terry_orders_by_wins():
    games = pd.DataFrame([{"p0": "a", "p1": "b", "winner": "a"}] * 3 + [{"p0": "b", "p1": "a", "winner": "b"}])
    r = bradley_terry(games, ["a", "b"])
    assert r["a"] > r["b"]
