"""Baselines run end to end and log replayable JSONL."""
from kagri.agents.baselines import GreedyAgent, RandomAgent
from kagri.runner import load_run, run_episode


def test_baselines_run(tmp_path):
    for agent in (RandomAgent(), GreedyAgent()):
        log = tmp_path / f"{agent.name}.jsonl"
        s = run_episode(agent, seed=1, log_path=log)
        assert s["days"] == 30
        run = load_run(log)
        assert len(run["days"]) == 30 and run["summary"]["profit"] == s["profit"]


def test_greedy_beats_random():
    g = sum(run_episode(GreedyAgent(), s)["profit"] for s in range(2))
    r = sum(run_episode(RandomAgent(), s)["profit"] for s in range(2))
    assert g > r
