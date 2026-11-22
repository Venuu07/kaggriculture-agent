"""Real-weather mode: drive a season with real historical daily weather for an Indian district.

Data: Open-Meteo historical archive (free, no API key). Each real day is mapped to the game's
weather: heavy rain (>= 15 mm), drought (hot and dry: evaporation exceeds rain by >= 6 mm, or
>= 38 °C with no rain), cloudy (light rain), otherwise sunny.

    python -m kagri.realweather --list
    python -m kagri.realweather --district anantapur --start 2025-07-01     # needs internet once
    python -m kagri.evaluate --weather anantapur_2025-07-01                 # then fully offline

Fetched seasons are cached in data/weather/ and appear in the UI's Live mode.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

import requests

from . import ROOT

WEATHER_DIR = ROOT / "data" / "weather"

DISTRICTS: dict[str, tuple[str, float, float]] = {
    "anantapur": ("Anantapur, Andhra Pradesh (semi-arid, drought-prone)", 14.68, 77.60),
    "guntur": ("Guntur, Andhra Pradesh (chilli and cotton belt)", 16.31, 80.44),
    "nashik": ("Nashik, Maharashtra (onion and grape belt)", 20.00, 73.79),
    "ludhiana": ("Ludhiana, Punjab (wheat and paddy)", 30.90, 75.85),
    "mysuru": ("Mysuru, Karnataka", 12.30, 76.64),
    "wayanad": ("Wayanad, Kerala (very wet monsoon)", 11.69, 76.08),
}

HEAVY_RAIN_MM = 15.0
LIGHT_RAIN_MM = 2.0
DRY_DEFICIT_MM = 6.0
HOT_C = 38.0


def classify_day(rain_mm: float, tmax_c: float, et0_mm: float) -> str:
    """Map one real day to the game's weather."""
    if rain_mm >= HEAVY_RAIN_MM:
        return "heavy_rain"
    if (et0_mm - rain_mm) >= DRY_DEFICIT_MM or (tmax_c >= HOT_C and rain_mm < 1.0):
        return "drought"
    if rain_mm >= LIGHT_RAIN_MM:
        return "cloudy"
    return "sunny"


def season_name(district: str, start: str) -> str:
    return f"{district}_{start}"


def fetch(district: str, start: str, days: int = 30) -> Path:
    """Download `days` days of real weather from `start` (YYYY-MM-DD) and cache the mapped season."""
    if district not in DISTRICTS:
        raise SystemExit(f"Unknown district '{district}'. Choose from: {', '.join(DISTRICTS)}")
    label, lat, lon = DISTRICTS[district]
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=days - 1)).isoformat()
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=60, params={
        "latitude": lat, "longitude": lon, "start_date": start, "end_date": end, "timezone": "Asia/Kolkata",
        "daily": "precipitation_sum,temperature_2m_max,et0_fao_evapotranspiration",
    })
    r.raise_for_status()
    daily = r.json()["daily"]
    rows = []
    for i, date in enumerate(daily["time"]):
        rain = float(daily["precipitation_sum"][i] or 0.0)
        tmax = float(daily["temperature_2m_max"][i] or 0.0)
        et0 = float(daily["et0_fao_evapotranspiration"][i] or 0.0)
        rows.append({"date": date, "rain_mm": rain, "tmax_c": tmax, "et0_mm": et0,
                     "weather": classify_day(rain, tmax, et0)})
    if len(rows) < days:
        raise SystemExit(f"Only {len(rows)} days returned; pick an earlier start date.")
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    path = WEATHER_DIR / f"{season_name(district, start)}.json"
    path.write_text(json.dumps({"district": district, "label": label, "lat": lat, "lon": lon, "start": start,
                                "source": "Open-Meteo historical archive (archive-api.open-meteo.com)",
                                "days": rows}, indent=1), encoding="utf-8")
    return path


def load_season(name: str) -> dict[str, Any]:
    """Load a cached real-weather season by name (e.g. 'anantapur_2025-07-01') or path."""
    path = Path(name)
    if not path.suffix:
        path = WEATHER_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Fetch it first: python -m kagri.realweather --district ... --start ...")
    return json.loads(path.read_text(encoding="utf-8"))


def cached_seasons() -> list[dict[str, Any]]:
    out = []
    for p in sorted(WEATHER_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        counts: dict[str, int] = {}
        for row in d["days"]:
            counts[row["weather"]] = counts.get(row["weather"], 0) + 1
        out.append({"name": p.stem, "label": d["label"], "start": d["start"], "counts": counts,
                    "rain_mm": round(sum(r["rain_mm"] for r in d["days"]), 1)})
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--district", choices=list(DISTRICTS))
    ap.add_argument("--start", default="2025-07-01", help="first day of the season, YYYY-MM-DD")
    ap.add_argument("--list", action="store_true", help="list districts and cached seasons")
    a = ap.parse_args(argv)
    if a.list or not a.district:
        print("Districts:")
        for k, (label, lat, lon) in DISTRICTS.items():
            print(f"  {k:<10} {label}  ({lat}, {lon})")
        print("Cached seasons:", [s["name"] for s in cached_seasons()] or "none yet")
        return
    path = fetch(a.district, a.start)
    season = load_season(str(path))
    counts: dict[str, int] = {}
    for row in season["days"]:
        counts[row["weather"]] = counts.get(row["weather"], 0) + 1
    print(f"Saved {path}\n{season['label']} from {a.start}: {counts}")


if __name__ == "__main__":
    main()
