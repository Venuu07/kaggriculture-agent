"""Real-weather mapping and the env hook. The numbers below are synthetic test inputs, not real data."""
import json

from kagri.env import FarmEnv
from kagri.realweather import classify_day


def test_classify_day_thresholds():
    assert classify_day(40.0, 29.0, 3.0) == "heavy_rain"
    assert classify_day(0.0, 39.0, 7.5) == "drought"
    assert classify_day(5.0, 31.0, 4.0) == "cloudy"
    assert classify_day(0.2, 32.0, 4.5) == "sunny"


def test_env_follows_a_weather_file(tmp_path):
    days = [{"date": f"2099-01-{i + 1:02d}", "rain_mm": 0.0, "tmax_c": 30.0, "et0_mm": 4.0,
             "weather": "drought" if i % 2 else "heavy_rain"} for i in range(30)]
    f = tmp_path / "synthetic_test.json"
    f.write_text(json.dumps({"label": "Synthetic test place", "start": "2099-01-01", "days": days}))
    env = FarmEnv(weather=str(f))
    obs = env.reset(0)
    assert obs["weather"]["weather"] == "heavy_rain" and obs["weather"]["real"]["date"] == "2099-01-01"
    obs, _, _, _ = env.step({})
    assert obs["weather"]["weather"] == "drought"
