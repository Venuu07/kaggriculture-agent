"""Basic FarmEnv behaviour."""
from kagri.env import FarmEnv
from kagri.plan import validate_plan


def _run(seed: int, plan: dict) -> float:
    env = FarmEnv()
    env.reset(seed)
    done = False
    while not done:
        _, _, done, _ = env.step(plan)
    return env.cash


def test_reset_observation():
    env = FarmEnv()
    obs = env.reset(0)
    assert obs["day"] == 0 and obs["cash"] == 3000 and obs["free_plots"] == 25
    assert set(obs["prices"]) >= {"WHEAT", "MELON", "EGG"}


def test_episode_has_30_days_and_ends():
    env = FarmEnv()
    env.reset(0)
    steps, done = 0, False
    while not done:
        _, _, done, _ = env.step({"plant": {"WHEAT": 5}, "sell": {"WHEAT": "all"}, "hands": 1})
        steps += 1
    assert steps == 30 and env.done


def test_deterministic_given_seed():
    plan = {"plant": {"CARROT": 10}, "sell": {"CARROT": "all"}, "hands": 2}
    assert _run(3, plan) == _run(3, plan)


def test_profitable_plan_makes_money():
    assert _run(0, {"plant": {"WHEAT": 25}, "sell": {"WHEAT": "all"}, "hands": 3}) > 3000


def test_invalid_actions_rejected_not_crash():
    env = FarmEnv()
    obs = env.reset(0)
    bad = {"plant": {"BANANA": 3, "WHEAT": "lots"}, "sell": {"MELON": 99}, "hands": -2,
           "buy_animals": {"DRAGON": 1}, "fly": True}
    _, _, done, info = env.step(bad)
    assert not done and len(info["rejected"]) >= 5
    _, _, _, info = env.step("not a plan")
    assert info["rejected"]


def test_budget_guardrail_trims_overspending():
    env = FarmEnv()
    obs = env.reset(0)
    clean, rej = validate_plan({"plant": {"STRAWBERRY": 25}, "buy_land": True}, obs)
    assert clean["buy_land"] and clean["plant"].get("STRAWBERRY", 0) <= 20
    assert any("trimmed" in r for r in rej)


def test_late_planting_rejected():
    env = FarmEnv()
    env.reset(0)
    for _ in range(25):
        env.step({})
    _, _, _, info = env.step({"plant": {"MELON": 3}})
    assert any("not be ready" in r for r in info["rejected"])


def test_simulate_does_not_change_real_env():
    env = FarmEnv()
    obs = env.reset(0)
    res = env.simulate({"plant": {"WHEAT": 10}, "hands": 2}, days=5)
    assert env.day == 0 and env.cash == obs["cash"]
    assert "net_worth_change" in res
